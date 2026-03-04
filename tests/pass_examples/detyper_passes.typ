#set page(
  margin: 10pt,
);
#set text(weight: "black")

#let pass(_name, _before, _after) = {
  grid(
    columns: (auto, 10pt, 1fr),
    [=== #_name],
    [],
    line(length: 100%, stroke: 1pt)
  )
  grid(
    columns: (2fr, 10pt, 20pt, 3fr),
    _before,
    [],
    [= $arrow$],
    _after
  )  
}

// -------- Primitives (box) --------

#let primitive_arg_before = ```python
foo(int64(1))
def foo(x: int64):
  return x + 1
```;

#let primitive_arg_after = ```python
foo(box(int64(1))) # box call site args
def foo(x):
  return int64(x) + 1 # wrap uses
```;

#let primitive_return_before = ```python
x = foo()
def foo() -> int64:
  return int64(1)
```;

#let primitive_return_after = ```python
x = int64(foo()) # wrap call sites
def foo():
  return box(int64(1)) # box return statement
```;

#let primitive_body_annotation_before = ```python
def foo():
  x: int64 = 1
  y: int64
  y = 1
  bar(x, y)
```;

#let primitive_body_annotation_after = ```python
def foo():
  x = box(int64(1)) # wrap assignment
  # delete bare annotation
  y = box(int64(1)) # wrap assignment
  bar(int64(x), int64(y)) # wrap uses
```;


// -------- CheckedList (construct) --------

#let chls_arg_before = ```python
xs = CheckedList[int64]([int64(1)])
bar(xs)

def bar(xs: CheckedList[int64]):
  xs.append(int64(2))
```;

#let chls_arg_after = ```python
def __repro_bar_arg0(f, arg0):
  _arg0 = CheckedList[int64](arg0)
  _out = f(_arg0)
  arg0.clear()
  arg0.extend(_arg0)
  return _out

xs = CheckedList[int64]([int64(1)])
__repro_bar_arg0(bar, xs)

def bar(xs):
  xs.append(int64(2))
```;

#let chls_return_before = ```python
x = foo()
def foo() -> CheckedList[int64]:
  return CheckedList[int64]([int64(1)])
```;

#let chls_return_after = ```python
x = CheckedList[int64](foo()) # wrap call sites
def foo():
  return CheckedList[int64]([int64(1)])
```;

#let chls_body_annotation_before = ```python
def foo():
  x: CheckedList[int64] =
    CheckedList[int64]([int64(1)])
  y: CheckedList[int64]
  y = CheckedList[int64]([int64(1)])
  bar(x, y)
```;

#let chls_body_annotation_after = ```python
def __repro_bar_arg0(f, arg0, arg1):
  _arg0 = CheckedList[int64](arg0)
  _out = f(_arg0, arg1)
  arg0.clear()
  arg0.extend(_arg0)
  return _out

def __repro___repro_bar_arg0_arg2(f, arg0, arg1, arg2):
  _arg2 = CheckedList[int64](arg2)
  _out = f(arg0, arg1, _arg2)
  arg2.clear()
  arg2.extend(_arg2)
  return _out

def foo():
  x = CheckedList[int64]([int64(1)])
  # delete bare annotation
  y = CheckedList[int64]([int64(1)])
  __repro___repro_bar_arg0_arg2(
    __repro_bar_arg0,
    bar, x, y)
```;


// -------- Cast All --------

#let cast_arg_before = ```python
foo(Variable("x", int64(0)))
def foo(v: Variable):
  return v.value
```;

#let cast_arg_after = ```python
foo(cast(Variable, Variable("x", int64(0)))) # wrap call site args
def foo(v):
  return cast(Variable, v).value # wrap uses
```;

#let cast_return_before = ```python
x = foo()
def foo() -> Variable:
  return Variable("x", int64(0))
```;

#let cast_return_after = ```python
x = cast(Variable, foo()) # wrap call sites
def foo():
  return Variable("x", int64(0))
```;

#let cast_body_annotation_before = ```python
def foo(v: Variable):
  x: Variable = v
  bar(x)
```;

#let cast_body_annotation_after = ```python
def foo(v: Variable):
  x = cast(Variable, v) # wrap assignment
  bar(cast(Variable, x)) # wrap uses
```;


// -------- Cast Container Passthrough --------

#let passthrough_arg_before = ```python
foo([Variable("x", int64(0))])
def foo(xs: List[Variable]):
  return xs[0].value
```;

#let passthrough_arg_after = ```python
foo(cast(List[Variable], [Variable("x", int64(0))])) # wrap call site args
def foo(xs):
  return cast(List[Variable], xs)[0].value # wrap uses
```;

#let passthrough_return_before = ```python
xs = foo()
def foo() -> List[Variable]:
  return [Variable("x", int64(0))]
```;

#let passthrough_return_after = ```python
xs = cast(List[Variable], foo()) # wrap call sites
def foo():
  return [Variable("x", int64(0))]
```;

#let passthrough_body_annotation_before = ```python
def foo(xs):
  ys: List[Variable] = xs
  bar(ys)
```;

#let passthrough_body_annotation_after = ```python
def foo(xs):
  ys = cast(List[Variable], xs) # wrap assignment
  bar(cast(List[Variable], ys)) # wrap uses
```;


// -------- None / symmetry no-op --------

#let none_return_before = ```python
def foo() -> None:
  return None
```;

#let none_return_after = ```python
def foo():
  return None
```;

#let param_none_before = ```python
def foo(x):
  return x
```;

#let param_none_after = ```python
def foo(x):
  return x
```;

#let body_none_before = ```python
def foo():
  x = 1
  return x
```;

#let body_none_after = ```python
def foo():
  x = 1
  return x
```;


// -------- Cleanup --------

#let cleanup_inline_before = ```python
@inline
def foo(_x):
  x: int64 = int64(_x)
  return x
```;

#let cleanup_inline_after = ```python
@inline
def foo(_x):
  return int64(_x)
```;

#let cleanup_checkedlist_return_before = ```python
x = CheckedList[int64](foo())
def foo():
  return CheckedList[int64]([int64(1)])
```;

#let cleanup_checkedlist_return_after = ```python
x = CheckedList[int64](foo())
def foo():
  return [int64(1)]
```;

#let cleanup_wrappers_before = ```python
a = int64(int64(x))
b = box(box(y))
c = cast(Variable, cast(Variable, z))
```;

#let cleanup_wrappers_after = ```python
a = int64(x)
b = box(y)
c = cast(Variable, z)
```;


#line(length: 100%, stroke: 1pt)
== Primitives

#pass(
  "Primitive Arg",
  primitive_arg_before,
  primitive_arg_after
)

#pass(
  "Primitive Return",
  primitive_return_before,
  primitive_return_after
)

#pass(
  "Primitive Body Annotation",
  primitive_body_annotation_before,
  primitive_body_annotation_after
)


#line(length: 100%, stroke: 1pt)
== Checked Types (Construct)

#pass(
  "CheckedList Arg",
  chls_arg_before,
  chls_arg_after
)

#pass(
  "CheckedList Return",
  chls_return_before,
  chls_return_after
)

#pass(
  "CheckedList Body Annotation",
  chls_body_annotation_before,
  chls_body_annotation_after
)


#line(length: 100%, stroke: 1pt)
== Cast Types

#pass(
  "Cast Arg",
  cast_arg_before,
  cast_arg_after
)

#pass(
  "Cast Return",
  cast_return_before,
  cast_return_after
)

#pass(
  "Cast Body Annotation",
  cast_body_annotation_before,
  cast_body_annotation_after
)


#line(length: 100%, stroke: 1pt)
== Container Passthrough (Cast)

#pass(
  "Passthrough Arg",
  passthrough_arg_before,
  passthrough_arg_after
)

#pass(
  "Passthrough Return",
  passthrough_return_before,
  passthrough_return_after
)

#pass(
  "Passthrough Body Annotation",
  passthrough_body_annotation_before,
  passthrough_body_annotation_after
)


#line(length: 100%, stroke: 1pt)
== None / No-op

#pass(
  "None Return",
  none_return_before,
  none_return_after
)

#pass(
  "Param Detype None (No-op)",
  param_none_before,
  param_none_after
)

#pass(
  "Body Detype None (No-op)",
  body_none_before,
  body_none_after
)


#line(length: 100%, stroke: 1pt)
== Cleanup Passes

#pass(
  "Cleanup Inline",
  cleanup_inline_before,
  cleanup_inline_after
)

#pass(
  "Cleanup CheckedList Return Wraps",
  cleanup_checkedlist_return_before,
  cleanup_checkedlist_return_after
)

#pass(
  "Cleanup Wrappers",
  cleanup_wrappers_before,
  cleanup_wrappers_after
)

