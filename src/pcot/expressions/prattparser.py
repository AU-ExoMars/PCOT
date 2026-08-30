"""
Pratt parser for expressions based on
https://journal.stuffwithstuff.com/2011/03/19/pratt-parsers-expression-parsing-made-easy/
https://github.com/KubaO/pybantam/blob/main/src/bantam.py
"""
from __future__ import annotations  # for python <3.13
from enum import Enum, auto
from io import BytesIO
from token import NUMBER
from tokenize import tokenize, TokenError, ENCODING, ENDMARKER, NEWLINE, STRING, NAME, TokenInfo
from typing import List, Any, Optional, Dict
from abc import ABC, abstractmethod
from logging import getLogger

logger = getLogger(__name__)

class ParserException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)

    @property
    def message(self):
        return self.args[0]

class TreeNodeType(Enum):
    NUMBER = auto(),    # a literal number
    STRING = auto(),    # a literal string
    NAME = auto(),      # an identifier, e.g. (but not always) a variable name
    BINOP = auto(),     # binary op
    UNOP = auto(),      # unary op (prefix or postfix)
    APPLY = auto(),     # used for both a[..] and a(...); func calls and indexing.
    VECTOR = auto(),    # a vector/array literal, e.g. [1,2,3]


class TreeNode:
    """
    The parser generates an abstract syntax tree (AST) made up of these nodes. The type is a string
    determining what kind of node this is, which also determines the meaning of the node's values.
    Some nodes have extra data determining their "subtype" (e.g. binary ops), some don't.
    """
    type: TreeNodeType           # type of node
    data: Any
    children: List[TreeNode]     # list of child values

    def __init__(self, type:TreeNodeType, data: Any=None, children: List[Any]=None) -> None:
        self.type = type
        self.data = data
        self.children = children if children is not None else []

    def __str__(self) -> str:
        return self.pretty()

    def pretty(self, indent: int = 0) -> str:
        pad = "  " * indent
        dstr = f": data={self.data}" if self.data else ""
        lines = [f"{pad}{self.type}{dstr}"]

        for i, v in enumerate(self.children):
            # Print the index, then the child subtree
            lines.append(f"{pad}  [{i}]")
            lines.append(v.pretty(indent + 2))

        return "\n".join(lines)


################# "Parselet" (subparser) core ADTs

class InfixParselet(ABC):
    """Called after the LHS has been parsed - used for infix (e.g. binary) operators; does postfix too."""
    precedence: int

    @abstractmethod
    def parse(self, parser: PrattParser, left: TreeNode, token: Token) -> TreeNode:
        pass


class PrefixParselet(ABC):
    """Associated with a token at the start of an expression; the parse method is called with
    the leading token (which has been consumed) and it parses things after that. Also used for
    single-token expressions like vars and constants."""
    @abstractmethod
    def parse(self, parser: PrattParser, token: Token) -> TreeNode:
        pass

################### Concrete parselets

class OperandParselet(PrefixParselet):
    """Parses leaf nodes - strings, numbers and identifiers"""
    def __init__(self, type: TreeNodeType) -> None:
        self.type = type
    def parse(self, parser: PrattParser, token: Token) -> TreeNode:
        return TreeNode(self.type, token)


class BinaryOperatorParselet(InfixParselet):
    def __init__(self, subtype:str, precedence:int, is_right_associative:bool) -> None:
        self.precedence = precedence
        self.subtype = subtype
        self.is_right_associative = is_right_associative

    def parse(self, parser: PrattParser, left: TreeNode, token: Token) -> TreeNode:
        """To handle right-assoc ops like ^, we allow a slightly lower precedence when
        parsing the RHS. If a parselet with the same precedence appears on the right,
        it will take this parselet's result as its LHS."""
        precedence = self.precedence-1 if self.is_right_associative else self.precedence
        right = parser.parse_expression(precedence)
        # putting the actual token on the right to (hopefully) force reverse Polish output
        return TreeNode(TreeNodeType.BINOP, self.subtype, [left, right])


class ApplicationParselet(InfixParselet):
    """Parselet for function calls <expr>(<expr>,<expr>...) but can also handle [] and {}."""
    def __init__(self, subtype: str, closing:str) -> None:
        self.subtype = subtype
        self.closing = closing
        self.precedence = 10000

    def parse(self, parser: PrattParser, left: TreeNode, token: Token) -> TreeNode:
        args: List[TreeNode] = []
        if not parser.match(self.closing):   # might be no arguments!
            while True:
                args.append(parser.parse_expression())
                if not parser.match(","):
                    break
            parser.next(self.closing)
        # in the resulting tree, the data is None but the last child is used to hold
        # the function - the function might not be a literal function name but an expression
        # itself. We use the last to make DFS come out as reverse polish.
        return TreeNode(TreeNodeType.APPLY, data=self.subtype, children=args+[left])


class PostfixOperatorParselet(InfixParselet):
    """Not currently used, but could be useful in the future. Parses postfix unary
    operators, such as factorial."""
    def __init__(self, subtype:str, precedence:int) -> None:
        self.subtype = subtype
        self.precedence = precedence

    def parse(self, parser: PrattParser, left: TreeNode, token: Token) -> TreeNode:
        return TreeNode(TreeNodeType.UNOP, self.subtype, children=[left])


class VectorParselet(PrefixParselet):
    """Parses vector/array literals like [1,2,3]. Elements are full expressions, so
    something like [1,2,3,2*2,a*b] works fine."""
    def __init__(self, closing: str) -> None:
        self.closing = closing

    def parse(self, parser: PrattParser, token: Token) -> TreeNode:
        elements: List[TreeNode] = []
        if not parser.match(self.closing):   # might be empty!
            while True:
                elements.append(parser.parse_expression())
                if not parser.match(","):
                    break
            parser.next(self.closing)
        return TreeNode(TreeNodeType.VECTOR, children=elements)


class GroupParselet(PrefixParselet):
    """
    Used to handle bracket parsing - does not generate its own TreeNode, just returns
    the treenode generated for the expression in the brackets.
    """
    def parse(self, parser: PrattParser, token: Token) -> TreeNode:
        expression = parser.parse_expression()
        parser.next(")")
        return expression


class PrefixOperatorParselet(PrefixParselet):
    """Parses prefix unary operators"""
    def __init__(self, subtype:str, precedence:int) -> None:
        self.subtype = subtype
        self.precedence = precedence

    def parse(self, parser: PrattParser, token: Token) -> TreeNode:
        right = parser.parse_expression(self.precedence)
        return TreeNode(TreeNodeType.UNOP, self.subtype, [right])


class TreeVisitor(ABC):
    def visit(self, node: TreeNode, output:Optional[List[Any]] = None):
        """We assume that the language we are generating code for is a stack language.
        Walk over the tree in a depth-first manner, calling methods for each node type to
        generate instructions."""
        if output is None:
            output = []
        for child in node.children:
            self.visit(child, output)
        if node.type == TreeNodeType.NUMBER:
            v = self.generate_number(node.data)
        elif node.type == TreeNodeType.STRING:
            v = self.generate_string(node.data)
        elif node.type ==  TreeNodeType.NAME:
            v = self.generate_name(node.data)
        elif node.type == TreeNodeType.BINOP:
            v = self.generate_binop(node.data)
        elif node.type == TreeNodeType.UNOP:
            v = self.generate_unop(node.data)
        elif node.type == TreeNodeType.APPLY:
            v = self.generate_apply(node.data, len(node.children))
        elif node.type == TreeNodeType.VECTOR:
            v = self.generate_vector(len(node.children))
        else:
            raise NotImplementedError(f"Unknown node type: {node.type}")
        output.append(v)
        return output

    @abstractmethod
    def generate_number(self, data:Any) -> Any:
        """Create instruction to stack a number"""
        pass
    @abstractmethod
    def generate_string(self, data:Any) -> Any:
        """Create instruction to stack a string"""
        pass
    @abstractmethod
    def generate_name(self, data:Any) -> Any:
        """Create instruction to process an identifier e.g. a variable fetch"""
        pass
    @abstractmethod
    def generate_binop(self, data:Any) -> Any:
        """Create instruction to handle a binary operator"""
        pass
    @abstractmethod
    def generate_unop(self, data:Any) -> Any:
        """Create instruction to handle an unary operator"""
        pass
    @abstractmethod
    def generate_apply(self, data:Any, child_count:int) -> Any:
        """Create instruction to handle application, e.g. function call or
        indexing. The top item on the stack is the callee, the others are the args
        which will need to be popped in reverse order."""
        pass
    @abstractmethod
    def generate_vector(self, child_count:int) -> Any:
        """Create instruction to build a vector from the top `data` items on the stack"""
        pass


################## Tokenisation, based on the Python tokeniser

def _dequote(s):
    """Remove quotes from a string if it's quoted and the quotes match"""
    if (len(s) >= 2 and s[0] == s[-1]) and s.startswith(("'", '"')):
        return s[1:-1]
    return s

class Token:
    type: str
    value: str
    start: int
    end: int

    def __init__(self, t: TokenInfo):
        self.line = t.line
        self.start = t.start[1]
        self.end = t.end[1]
        if t.type == NAME:
            self.type = "name"
            self.value = t.string
        elif t.type == NUMBER:
            self.type = "number"
            self.value = t.string
        elif t.type == STRING:
            self.type = "string"
            self.value = _dequote(t.string)
        else:
            self.type = t.string
            self.value = t.string

    def __str__(self) -> str:
        return f"Token(type={self.type}, value={self.value}, start={self.start}, end={self.end})"

    def __repr__(self) -> str:
        return str(self)


################### Main parser

class PrattParser:

    toks: List[Token]
    # the two dictionaries of tokens and their parsers, keyed token string
    prefix_parselets: Dict[str,PrefixParselet]
    infix_parselets: Dict[str,InfixParselet]

    def __init__(self) -> None:
        self.prefix_parselets = {}
        self.infix_parselets = {}
        # register parselets for builtin tokens, subclasses may add others.
        self.register("name", OperandParselet(TreeNodeType.NAME))
        self.register("number", OperandParselet(TreeNodeType.NUMBER))
        self.register("string", OperandParselet(TreeNodeType.STRING))
        self.register("(", GroupParselet())
        self.register("(", ApplicationParselet("call",")"))
        self.register("[", ApplicationParselet("index","]"))
        self.register("[", VectorParselet("]"))

    def parse(self, s: str) -> TreeNode:
        """Tokenise the input string into our Token objects and parse it, returning an ADT of TreeNode
        objects we can run a TreeVisitor on."""
        s = s.replace('\n', '').replace('\r', '')  # remove rogue newlines
        x = BytesIO(s.encode())
        try:
            self.toks = [Token(x) for x in (tokenize(x.readline) or []) if x.type != ENCODING
                         and x.type != ENDMARKER and
                         x.type != NEWLINE]
        except TokenError:
            raise ParserException(f"Unexpected end of input")

        result = self.parse_expression(precedence=0)
        if self.toks_left():
            raise ParserException(f"Unexpected token '{self.toks[0].value}'")
        return result

    def parse_expression(self,precedence: int=0) -> TreeNode:
        # get the first token, which must correspond to a prefix parselet.
        token = self.next()
        prefix = self.prefix_parselets.get(token.type, None)
        if not prefix:
            raise ParserException(f"Could not parse token '{token.value}'")
        # parse it
        left = prefix.parse(self, token)
        # do the magic Pratt parsing stuff - get tokens
        while precedence < self._get_precedence():
            token = self.next()
            infix = self.infix_parselets.get(token.type, None)
            left = infix.parse(self, left, token)
        return left

    def register(self, token: str, parselet: InfixParselet|PrefixParselet) -> None:
        if isinstance(parselet, PrefixParselet):
            self.prefix_parselets[token] = parselet
        elif isinstance(parselet, InfixParselet):
            self.infix_parselets[token] = parselet
        else:
            raise NotImplementedError(f"Unknown parselet type {type(parselet)}")

    def register_infix_left_associative(self, token:str, precedence: int) -> None:
        self.register(token, BinaryOperatorParselet(token, precedence,False))

    def register_infix_right_associative(self, token: str, precedence: int) -> None:
        self.register(token, BinaryOperatorParselet(token, precedence,True))

    def register_prefix(self, token: str, precedence: int) -> None:
        self.register(token, PrefixOperatorParselet(token, precedence))

    def register_postfix(self, token: str, precedence: int) -> None:
        self.register(token, PostfixOperatorParselet(token, precedence))

    ############################### Internals

    def _get_precedence(self) -> int:
        """Get the precedence of the current token, or zero if there is no infix parser"""
        tok = self.peek()
        if not tok:
            return 0
        parser:InfixParselet = self.infix_parselets.get(tok.type, None)
        return parser.precedence if parser else 0

    def next(self, expected:Optional[str]=None) -> Optional[Token]:
        """internal method - get next token"""
        if self.toks_left():
            logger.debug(f"Next token : {self.toks[0]}")
            t = self.toks.pop(0)
            if expected is None:
                return t
            elif isinstance(expected, str):
                if t.type != expected:
                    raise ParserException(f"Unexpected token '{t.value}'")
                return t
            else:
                raise NotImplementedError(f"Unexpected 'expected' token type'{expected}'")
        else:
            logger.error("Not sure about this.")
            return None

    def rewind(self, tok: Token):
        """tokeniser rewinder, put token back into input stream"""
        self.toks.insert(0, tok)

    def peek(self) -> Optional[Token]:
        """tokeniser peek, unused"""
        if self.toks_left():
            logger.debug(f"Peek token : {self.toks[0]}")
            return self.toks[0]
        else:
            return None

    def match(self, t: str):
        """Get the next token; if it is what we passed in (as a string), consume and return true, otherwise return false"""
        tok = self.next()
        if tok.type == t:
            return True
        else:
            self.rewind(tok)
            return False


    def toks_left(self) -> bool:
        """count remaining tokens"""
        return len(self.toks) > 0




class TestVisitor(TreeVisitor):
    def generate_number(self, data: Any) -> Any:
        return f"num:{data.value}"
    def generate_string(self, data: Any) -> Any:
        return f'string:"{data.value}"'
    def generate_name(self, data: Any) -> Any:
        return f'name:"{data.value}"'
    def generate_binop(self, data: Any) -> Any:
        return f"binop:{data}"
    def generate_unop(self, data: Any) -> Any:
        return f"unop:{data}"
    def generate_apply(self, data: Any, child_count:int) -> Any:
        return f"{data}:n={child_count}"
    def generate_vector(self,  child_count:int) -> Any:
        return f"vector:n={child_count}"



def main():
    parser = PrattParser()

    while True:
        a = input().strip()
        if not a or len(a)==0:
            break
        try:
            e = parser.parse(a)
            out = TestVisitor().visit(e)
            print(out)
            print(" ".join(out))
        except ParserException as ex:
            print(f"Error: {ex.message}")


if __name__ == "__main__":
    main()