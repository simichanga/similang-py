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
  %".8" = icmp eq i32 %".7", 5
  br i1 %".8", label %"for_loop_entry_1.if", label %"for_loop_entry_1.endif"
for_loop_otherwise_1:
  %".28" = load i32, i32* %".2"
  ret i32 %".28"
for_loop_entry_1.if:
  br label %"for_loop_otherwise_1"
for_loop_entry_1.endif:
  %".11" = load i32, i32* %".4"
  %".12" = icmp eq i32 %".11", 2
  br i1 %".12", label %"for_loop_entry_1.endif.if", label %"for_loop_entry_1.endif.endif"
for_loop_entry_1.endif.if:
  br label %"for_loop_entry_1"
for_loop_entry_1.endif.endif:
  %".15" = load i32, i32* %".4"
  %".16" = alloca [9 x i8]*
  store [9 x i8]* @"__str_2", [9 x i8]** %".16"
  %".18" = bitcast [9 x i8]* @"__str_2" to i8*
  %".19" = call i32 (i8*, ...) @"printf"(i8* %".18", i32 %".15")
  %".20" = load i32, i32* %".4"
  store i32 %".20", i32* %".2"
  %".22" = load i32, i32* %".4"
  %".23" = add i32 %".22", 1
  store i32 %".23", i32* %".4"
  %".25" = load i32, i32* %".4"
  %".26" = icmp slt i32 %".25", 10
  br i1 %".26", label %"for_loop_entry_1", label %"for_loop_otherwise_1"
}

@"__str_2" = internal constant [9 x i8] c"i = %i\0a\00\00"