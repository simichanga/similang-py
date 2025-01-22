; ModuleID = "main"
target triple = "unknown-unknown-unknown"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i1 @"main"()
{
main_entry:
  %".2" = sitofp i32 1 to float
  %".3" = fadd float %".2", 0x4004000000000000
  %".4" = alloca float
  store float %".3", float* %".4"
  %".6" = load float, float* %".4"
  %".7" = alloca [9 x i8]*
  store [9 x i8]* @"__str_1", [9 x i8]** %".7"
  %".9" = bitcast [9 x i8]* @"__str_1" to i8*
  %".10" = call i32 (i8*, ...) @"printf"(i8* %".9", float %".6")
  %".11" = load float, float* %".4"
  %".12" = fcmp ogt float %".11", 0x400c000000000000
  ret i1 %".12"
}

@"__str_1" = internal constant [9 x i8] c"a = %f\0a\00\00"