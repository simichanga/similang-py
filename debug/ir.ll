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
  %".4" = alloca i32
  store i32 22, i32* %".4"
  %".6" = alloca float
  store float 0x400c000000000000, float* %".6"
  %".8" = load [5 x i8]*, [5 x i8]** %".2"
  %".9" = load i32, i32* %".4"
  %".10" = alloca [20 x i8]*
  store [20 x i8]* @"__str_2", [20 x i8]** %".10"
  %".12" = bitcast [20 x i8]* @"__str_2" to i8*
  %".13" = call i32 (i8*, ...) @"printf"(i8* %".12", [5 x i8]* %".8", i32 %".9")
  ret i32 0
}

@"__str_1" = internal constant [5 x i8] c"John\00"
@"__str_2" = internal constant [20 x i8] c"%s is %d years old.\00"