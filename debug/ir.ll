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
  %".4" = load i32, i32* %".2"
  ret i32 %".4"
}
