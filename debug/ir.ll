; ModuleID = "main"
target triple = "unknown-unknown-unknown"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"main"()
{
main_entry:
  %".2" = alloca [5 x i8]*
  store [5 x i8]* @"__str_1", [5 x i8]** %".2"
  %".4" = add i32 18, 5
  %".5" = alloca i32
  store i32 %".4", i32* %".5"
  %".7" = load [5 x i8]*, [5 x i8]** %".2"
  %".8" = load i32, i32* %".5"
  %".9" = alloca [20 x i8]*
  store [20 x i8]* @"__str_2", [20 x i8]** %".9"
  %".11" = bitcast [20 x i8]* @"__str_2" to i8*
  %".12" = call i32 (i8*, ...) @"printf"(i8* %".11", [5 x i8]* %".7", i32 %".8")
  ret i32 0
}

@"__str_1" = internal constant [5 x i8] c"John\00"
@"__str_2" = internal constant [20 x i8] c"%s is %i years old.\00"