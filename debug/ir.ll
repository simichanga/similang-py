; ModuleID = "main"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"foo"(i32 %".1", i32 %".2")
{
foo_entry:
  %".4" = alloca i32
  store i32 %".1", i32* %".4"
  %".6" = alloca i32
  store i32 %".2", i32* %".6"
  %".8" = load i32, i32* %".4"
  %".9" = load i32, i32* %".6"
  %".10" = add i32 %".8", %".9"
  ret i32 %".10"
}

define i32 @"main"()
{
main_entry:
  %".2" = call i32 @"foo"(i32 1, i32 2)
  %".3" = alloca [7 x i8]*
  store [7 x i8]* @"__str_1", [7 x i8]** %".3"
  %".5" = bitcast [7 x i8]* @"__str_1" to i8*
  %".6" = call i32 (i8*, ...) @"printf"(i8* %".5", i32 %".2")
  ret i32 0
}

@"__str_1" = internal constant [7 x i8] c"Foo %i\00"