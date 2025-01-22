; ModuleID = "main"
target triple = "unknown-unknown-unknown"
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
  %".13" = icmp slt i32 %".12", 10
  br i1 %".13", label %"while_loop_entry_2", label %"while_loop_otherwise_2"
while_loop_entry_2:
  %".15" = load i32, i32* %".5"
  %".16" = alloca [9 x i8]*
  store [9 x i8]* @"__str_3", [9 x i8]** %".16"
  %".18" = bitcast [9 x i8]* @"__str_3" to i8*
  %".19" = call i32 (i8*, ...) @"printf"(i8* %".18", i32 %".15")
  %".20" = load i32, i32* %".5"
  %".21" = call i32 @"add"(i32 %".20", i32 1)
  store i32 %".21", i32* %".5"
  %".23" = load i32, i32* %".5"
  %".24" = icmp slt i32 %".23", 10
  br i1 %".24", label %"while_loop_entry_2", label %"while_loop_otherwise_2"
while_loop_otherwise_2:
  %".26" = load i32, i32* %".5"
  ret i32 %".26"
}

@"__str_1" = internal constant [21 x i8] c"a starts off as %i\0a\00\00"
@"__str_3" = internal constant [9 x i8] c"a = %i\0a\00\00"