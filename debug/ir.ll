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
  %".2" = mul i32 2, 3
  %".3" = add i32 1, %".2"
  %".4" = sub i32 %".3", 7
  %".5" = alloca i32
  store i32 %".4", i32* %".5"
  %".7" = load i32, i32* %".5"
  %".8" = alloca [21 x i8]*
  store [21 x i8]* @"__str_1", [21 x i8]** %".8"
  %".10" = bitcast [21 x i8]* @"__str_1" to i8*
  %".11" = call i32 (i8*, ...) @"printf"(i8* %".10", i32 %".7")
  %".12" = load i32, i32* %".5"
  %".13" = icmp eq i32 %".12", 0
  br i1 %".13", label %"main_entry.if", label %"main_entry.else"
main_entry.if:
  %".15" = load i32, i32* %".5"
  %".16" = icmp slt i32 %".15", 10
  br i1 %".16", label %"while_loop_entry_2", label %"while_loop_otherwise_2"
main_entry.else:
  %".30" = alloca [8 x i8]*
  store [8 x i8]* @"__str_4", [8 x i8]** %".30"
  %".32" = bitcast [8 x i8]* @"__str_4" to i8*
  %".33" = call i32 (i8*, ...) @"printf"(i8* %".32")
  br label %"main_entry.endif"
main_entry.endif:
  %".35" = icmp eq i32 1, 0
  br i1 %".35", label %"while_loop_entry_5", label %"while_loop_otherwise_5"
while_loop_entry_2:
  %".18" = load i32, i32* %".5"
  %".19" = alloca [9 x i8]*
  store [9 x i8]* @"__str_3", [9 x i8]** %".19"
  %".21" = bitcast [9 x i8]* @"__str_3" to i8*
  %".22" = call i32 (i8*, ...) @"printf"(i8* %".21", i32 %".18")
  %".23" = load i32, i32* %".5"
  %".24" = call i32 @"add"(i32 %".23", i32 1)
  store i32 %".24", i32* %".5"
  %".26" = load i32, i32* %".5"
  %".27" = icmp slt i32 %".26", 10
  br i1 %".27", label %"while_loop_entry_2", label %"while_loop_otherwise_2"
while_loop_otherwise_2:
  br label %"main_entry.endif"
while_loop_entry_5:
  %".37" = icmp eq i32 1, 0
  br i1 %".37", label %"while_loop_entry_5", label %"while_loop_otherwise_5"
while_loop_otherwise_5:
  %".39" = load i32, i32* %".5"
  ret i32 %".39"
}

@"__str_1" = internal constant [21 x i8] c"a starts off as %i\0a\00\00"
@"__str_3" = internal constant [9 x i8] c"a = %i\0a\00\00"
@"__str_4" = internal constant [8 x i8] c"prank\0a\00\00"