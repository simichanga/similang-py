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
  %".4" = alloca i32
  store i32 0, i32* %".4"
  br label %"for_loop_entry_1"
for_loop_entry_1:
  %".7" = load i32, i32* %".4"
  %".8" = load i32, i32* %".2"
  %".9" = add i32 %".8", %".7"
  store i32 %".9", i32* %".2"
  %".11" = load i32, i32* %".4"
  %".12" = add i32 %".11", 1
  store i32 %".12", i32* %".4"
  %".14" = load i32, i32* %".4"
  %".15" = icmp slt i32 %".14", 10
  br i1 %".15", label %"for_loop_entry_1", label %"for_loop_otherwise_1"
for_loop_otherwise_1:
  %".17" = load i32, i32* %".2"
  %".18" = alloca [13 x i8]*
  store [13 x i8]* @"__str_2", [13 x i8]** %".18"
  %".20" = bitcast [13 x i8]* @"__str_2" to i8*
  %".21" = call i32 (i8*, ...) @"printf"(i8* %".20", i32 %".17")
  ret i32 0
}

@"__str_2" = internal constant [13 x i8] c"Suma este %i\00"