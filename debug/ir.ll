; ModuleID = "main"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"add"(i32 %".1", i32 %".2")
{
add_entry:
  %".4" = alloca i32
  store i32 %".1", i32* %".4"
  %".6" = alloca i32
  store i32 %".2", i32* %".6"
  %".8" = load i32, i32* %".4"
  %".9" = load i32, i32* %".6"
  %".10" = add i32 %".8", %".9"
  ret i32 %".10"
}

define i32 @"main"()
{
main_entry:
  %".2" = alloca i32
  store i32 0, i32* %".2"
  store i32 0, i32* %".2"
  %".5" = load i32, i32* %".2"
  %".6" = icmp eq i32 %".5", 0
  br i1 %".6", label %"main_entry.if", label %"main_entry.else"
main_entry.if:
  %".8" = load i32, i32* %".2"
  %".9" = icmp slt i32 %".8", 10
  br i1 %".9", label %"while_loop_entry_1", label %"while_loop_otherwise_1"
main_entry.else:
  %".23" = alloca [8 x i8]*
  store [8 x i8]* @"__str_3", [8 x i8]** %".23"
  %".25" = bitcast [8 x i8]* @"__str_3" to i8*
  %".26" = call i32 (i8*, ...) @"printf"(i8* %".25")
  br label %"main_entry.endif"
main_entry.endif:
  %".28" = icmp eq i32 1, 0
  br i1 %".28", label %"while_loop_entry_4", label %"while_loop_otherwise_4"
while_loop_entry_1:
  %".11" = load i32, i32* %".2"
  %".12" = alloca [9 x i8]*
  store [9 x i8]* @"__str_2", [9 x i8]** %".12"
  %".14" = bitcast [9 x i8]* @"__str_2" to i8*
  %".15" = call i32 (i8*, ...) @"printf"(i8* %".14", i32 %".11")
  %".16" = load i32, i32* %".2"
  %".17" = call i32 @"add"(i32 %".16", i32 1)
  store i32 %".17", i32* %".2"
  %".19" = load i32, i32* %".2"
  %".20" = icmp slt i32 %".19", 10
  br i1 %".20", label %"while_loop_entry_1", label %"while_loop_otherwise_1"
while_loop_otherwise_1:
  br label %"main_entry.endif"
while_loop_entry_4:
  %".30" = icmp eq i32 1, 0
  br i1 %".30", label %"while_loop_entry_4", label %"while_loop_otherwise_4"
while_loop_otherwise_4:
  %".32" = load i32, i32* %".2"
  ret i32 %".32"
}

@"__str_2" = internal constant [9 x i8] c"a = %i\0a\00\00"
@"__str_3" = internal constant [8 x i8] c"prank\0a\00\00"