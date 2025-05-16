; ModuleID = "main"
target triple = "unknown-unknown-unknown"
target datalayout = ""

declare i32 @"printf"(i8* %".1", ...)

@"true" = constant i1 1
@"false" = constant i1 0
define i32 @"factorial"(i32 %".1")
{
factorial_entry:
  %".3" = alloca i32
  store i32 %".1", i32* %".3"
  %".5" = load i32, i32* %".3"
  %".6" = icmp eq i32 %".5", 0
  br i1 %".6", label %"factorial_entry.if", label %"factorial_entry.endif"
factorial_entry.if:
  ret i32 1
factorial_entry.endif:
  %".9" = load i32, i32* %".3"
  %".10" = load i32, i32* %".3"
  %".11" = sub i32 %".10", 1
  %".12" = call i32 @"factorial"(i32 %".11")
  %".13" = mul i32 %".9", %".12"
  ret i32 %".13"
}

define void @"main"()
{
main_entry:
  %".2" = alloca i32
  store i32 2, i32* %".2"
  %".4" = sitofp i32 3 to float
  %".5" = fadd float %".4", 0x3ff0000000000000
  %".6" = load i32, i32* %".2"
  %".7" = sitofp i32 %".6" to float
  %".8" = fadd float %".7", %".5"
  %".9" = fptosi float %".8" to i32
  store i32 %".9", i32* %".2"
  %".11" = load i32, i32* %".2"
  %".12" = call i32 @"factorial"(i32 %".11")
  %".13" = alloca i32
  store i32 %".12", i32* %".13"
  %".15" = load i32, i32* %".2"
  %".16" = load i32, i32* %".13"
  %".17" = alloca [27 x i8]*
  store [27 x i8]* @"__str_1", [27 x i8]** %".17"
  %".19" = bitcast [27 x i8]* @"__str_1" to i8*
  %".20" = call i32 (i8*, ...) @"printf"(i8* %".19", i32 %".15", i32 %".16")
  %".21" = alloca float
  store float 0x400921cac0000000, float* %".21"
  %".23" = load float, float* %".21"
  %".24" = load float, float* %".21"
  %".25" = fcmp olt float %".24", 0x4010000000000000
  %".26" = alloca [41 x i8]*
  store [41 x i8]* @"__str_2", [41 x i8]** %".26"
  %".28" = bitcast [41 x i8]* @"__str_2" to i8*
  %".29" = fpext float %".23" to double
  %".30" = call i32 (i8*, ...) @"printf"(i8* %".28", double %".29", i1 %".25")
  %".31" = alloca i1
  store i1 0, i1* %".31"
  %".33" = load i1, i1* %".31"
  %".34" = zext i1 0 to i32
  %".35" = zext i1 %".33" to i32
  %".36" = icmp eq i32 %".34", %".35"
  %".37" = alloca [19 x i8]*
  store [19 x i8]* @"__str_3", [19 x i8]** %".37"
  %".39" = bitcast [19 x i8]* @"__str_3" to i8*
  %".40" = call i32 (i8*, ...) @"printf"(i8* %".39", i1 %".36")
  ret void
}

@"__str_1" = internal constant [27 x i8] c"Factorial de %i este %i \0a\00\00"
@"__str_2" = internal constant [41 x i8] c"Numarul %f este mai mic decat 4.0? %b \0a\00\00"
@"__str_3" = internal constant [19 x i8] c"Lmao este true? %b\00"