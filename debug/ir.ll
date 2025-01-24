; ModuleID = "main"
target triple = "unknown-unknown-unknown"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"main"()
{
main_entry:
  %".2" = add i32 1, 2
  %".3" = alloca i32
  store i32 %".2", i32* %".3"
  %".5" = load i32, i32* %".3"
  %".6" = add i32 %".5", 3
  %".7" = alloca i32
  store i32 %".6", i32* %".7"
  %".9" = load i32, i32* %".7"
  ret i32 %".9"
}
