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
  %".7" = load i32, i32* %".2"
  %".8" = load i32, i32* %".4"
  %".9" = add i32 %".7", %".8"
  %".10" = load i32, i32* %".2"
  store i32 %".9", i32* %".2"
  %".12" = load i32, i32* %".4"
  %".13" = add i32 %".12", 1
  store i32 %".13", i32* %".4"
  %".15" = load i32, i32* %".4"
  %".16" = icmp slt i32 %".15", 100000
  br i1 %".16", label %"for_loop_entry_1", label %"for_loop_otherwise_1"
for_loop_otherwise_1:
  %".18" = load i32, i32* %".2"
  %".19" = alloca [11 x i8]*
  store [11 x i8]* @"__str_2", [11 x i8]** %".19"
  %".21" = bitcast [11 x i8]* @"__str_2" to i8*
  %".22" = call i32 (i8*, ...) @"printf"(i8* %".21", i32 %".18")
  ret i32 0
}

@"__str_2" = internal constant [11 x i8] c"Sum = %i\0a\00\00"