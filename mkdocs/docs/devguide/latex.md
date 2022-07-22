# A quick test of LaTeX support
LaTeX in these documents is handled with the pymdownx.arithmatex plugin, which really just hands
processing off to MathJax. MathJax then renders the LaTeX using JavaScript. Lots and lots of 
very clever JavaScript.

Here are some tests:


Inline equation: $y = \sigma\left(b+\sum_i w_i x_i (1+h) s_i\right)$ should work.

```
Inline equation: $y = \sigma\left(b+\sum_i w_i x_i (1+h) s_i\right)$ should work.
```

---


Block equations. This has to use double-backslash:
\\[
y =  \sigma\left(b+\sum_i w_i x_i (1+h) s_i\right)
\\]
```
\\[
y =  \sigma\left(b+\sum_i w_i x_i (1+h) s_i\right)
\\]
```

but this one doesn't:

\begin{equation}
f(1,0)=1 \iff w_1 \ge -b \label{eq:f101}
\end{equation}
```
\begin{equation}
f(1,0)=1 \iff w_1 \ge -b \label{eq:f101}
\end{equation}
```

---
Align. Note that the reference doesn't work!

\begin{align}
f(x,y) &= H (b+w_1 x + w_2 y)&\text{(Eq.~\ref{eq:f101})}\\
0 &= H(b+w_1+w_2)&\text{(subst.)}\\
H(b+w_1+w_2) &= 0\label{eq:f110in}\\
b+w_1+w_2 & < 0 & \text{(Heaviside step)}\\
w_1+w_2 & < -b.
\end{align}
```
\begin{align}
f(x,y) &= H (b+w_1 x + w_2 y)&\text{(Eq.~\ref{eq:f101})}\\
0 &= H(b+w_1+w_2)&\text{(subst.)}\\
H(b+w_1+w_2) &= 0\label{eq:f110in}\\
b+w_1+w_2 & < 0 & \text{(Heaviside step)}\\
w_1+w_2 & < -b.
\end{align}
```

---

Matrix. Note I've had to wrap in an equation.

\begin{equation}
X=
\left(\begin{matrix}
1 & 2 & 1\\
2 & 4 & 2\\
1 & 2 & 1
\end{matrix}\right)
\end{equation}
```
\begin{equation}
X=
\left(\begin{matrix}
1 & 2 & 1\\
2 & 4 & 2\\
1 & 2 & 1
\end{matrix}\right)
\end{equation}

```
