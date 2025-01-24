; ModuleID = "main"
target triple = "unknown-unknown-unknown"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"main"()
{
main_entry:
  %".2" = alloca i32
  store i32 0, i32* %".2"
  br label %"for_loop_entry_1"
for_loop_entry_1:
  %".5" = load i32, i32* %".2"
  %".6" = alloca [9 x i8]*
  store [9 x i8]* @"__str_2", [9 x i8]** %".6"
  %".8" = bitcast [9 x i8]* @"__str_2" to i8*
  %".9" = call i32 (i8*, ...) @"printf"(i8* %".8", i32 %".5")
  %".10" = load i32, i32* %".2"
  %".11" = add i32 %".10", 1
  %".12" = load i32, i32* %".2"
  store i32 %".11", i32* %".2"
  %".14" = load i32, i32* %".2"
  %".15" = icmp slt i32 %".14", 10
  br i1 %".15", label %"for_loop_entry_1", label %"for_loop_otherwise_1"
for_loop_otherwise_1:
  ret i32 0
}

@"__str_2" = internal constant [9 x i8] c"i = %i\0a\00\00"