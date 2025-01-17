; ModuleID = "main"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

define i32 @"main"()
{
main_entry:
  %".2" = alloca i32
  store i32 4, i32* %".2"
  %".4" = load i32, i32* %".2"
  %".5" = mul i32 %".4", 2
  ret i32 %".5"
}
