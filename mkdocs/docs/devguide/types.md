# Notes on types

Built-in types of data (i.e. of Datum objects) are kept in **datum.py**.

A type specifies:

* its name
* whether it is an image subtype (it's tricky to write a method for this,
since ImgType is defined after Type)
* whether it is an "internal type" used in the expression evaluator and not for connections
(e.g. IdentType, FuncType and NoneType)
* optional serialisation and deserialisation methods, taking and returning Datum

The Datum class has a type list, which contains singletons of all the type
objects. To register a type:

* create a type object
* append to the Datum types list
* if required, register a connector brush with connbrushes.register.
* Deal with binary and unary operators in expr expressions (see below).

## Operators

@@@info
Work in progress
@@@

Previously operators were entirely hardwired in utils.ops. This stopped us
creating new types. We could define something like binop(self,other) in
the type classes, but this wouldn't allow us to add new types as the RHS
for operations which have built-in types as the LHS.

The Simplest Thing That Can Possibly Work is a dictionary of operation functions
keyed (in the case of binops) by a tuple of types.

So this is how operators work now, relying on two registration processes.

The first is the registration of the operator lexeme (e.g. "*" or "+")
and precedence, and an associated function to call. This happens
as part of Parser. The function calls a binop() function in the ops
module, passing in the operator ID.

The second is the registration of operator ID (e.g. Operator.ADD)
and types in the ops module, with an associated function to call. This
is often a wrapper function around a lambda: the wrapper knows to
unpack (say) image and number data, and the lambda says they should
be processed with addition.

## Adding a new type with operator semantics

* Create a subclass of datum.Type
* add serialisation methods if required
* call Datum.registerType() with the type
* If required, add a new connector brush with connbrushes.register()
* To use the type, use the Type object with the Datum constructor and
Datum.get() method.

Adding operator semantics

* call ops.registerBinop and ops.registerUnop to register functions
to perform the required operations. The function should take Datum
objects and return a Datum.