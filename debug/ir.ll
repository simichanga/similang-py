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
  %".10" = load i32, i32* %".8"
  %".11" = add i32 %".10", 2
  store i32 %".11", i32* %".8"
  %".13" = fadd float 0x3ff3333340000000, 0x4002666660000000
  %".14" = alloca float
  store float %".13", float* %".14"
  %".16" = load [5 x i8]*, [5 x i8]** %".2"
  %".17" = load i32, i32* %".8"
  %".18" = load float, float* %".14"
  %".19" = alloca [31 x i8]*
  store [31 x i8]* @"__str_2", [31 x i8]** %".19"
  %".21" = bitcast [31 x i8]* @"__str_2" to i8*
  %".22" = fpext float %".18" to double
  %".23" = call i32 (i8*, ...) @"printf"(i8* %".21", [5 x i8]* %".16", i32 %".17", double %".22")
  ret i32 0
}

@"__str_1" = internal constant [5 x i8] c"John\00"
@"__str_2" = internal constant [31 x i8] c"%s is %d years old.\0a num is %f\00"