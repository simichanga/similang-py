; ModuleID = "main"
target triple = "unknown-unknown-unknown"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"main"()
{
main_entry:
  %".2" = alloca i1
  store i1 1, i1* %".2"
  %".4" = load i1, i1* %".2"
  %".5" = zext i1 %".4" to i32
  ret i32 %".5"
}
