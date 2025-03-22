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
  %".4" = mul i32 2, 3
  %".5" = add i32 1, %".4"
  %".6" = add i32 %".5", 4
  %".7" = mul i32 %".6", 2
  %".8" = alloca i32
  store i32 %".7", i32* %".8"
  %".10" = alloca float
  store float 0x400c000000000000, float* %".10"
  %".12" = load [5 x i8]*, [5 x i8]** %".2"
  %".13" = load i32, i32* %".8"
  %".14" = alloca [20 x i8]*
  store [20 x i8]* @"__str_2", [20 x i8]** %".14"
  %".16" = bitcast [20 x i8]* @"__str_2" to i8*
  %".17" = call i32 (i8*, ...) @"printf"(i8* %".16", [5 x i8]* %".12", i32 %".13")
  ret i32 0
}

@"__str_1" = internal constant [5 x i8] c"John\00"
@"__str_2" = internal constant [20 x i8] c"%s is %d years old.\00"