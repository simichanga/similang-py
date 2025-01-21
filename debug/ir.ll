; ModuleID = "main"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"main"()
{
main_entry:
  %".2" = alloca i32
  store i32 5, i32* %".2"
  %".4" = load i32, i32* %".2"
  %".5" = icmp eq i32 %".4", 5
  br i1 %".5", label %"main_entry.if", label %"main_entry.else"
main_entry.if:
  store i32 69, i32* %".2"
  br label %"main_entry.endif"
main_entry.else:
  store i32 420, i32* %".2"
  br label %"main_entry.endif"
main_entry.endif:
  %".11" = load i32, i32* %".2"
  ret i32 %".11"
}
