# IntegratedCompiling

Compile Code to Integrated Dynamics Variable Cards(Tested with few cases)

# Usage 使用方法

This script is used to compile Excel-formula like code to Integrated Dynamics Variable Card Sequence.

此脚本用于将类Excel公式的伪代码编译成动态联合中的变量卡序列。

Currently supported: only one input one output functions, something like:

目前仅支持一个输入一个输出的函数，类似这样：

```
func(in) := someLogic(var_exogenous, otherLogic(in), thirdLogic(var_exogenous, in))
```

It supports exogenous variables though(see example above), so it will satisfy most cases in Minecraft automation.

不过它支持输入外生变量（如上例）, 所以它可以满足大多数Minecraft自动化需求。

Example function above will be compiled to:

上面示例的这个函数会被编译成：

```
01. op_someLogic_1 := op_by_name("someLogic")  # 在逻辑编程器中选择Operator(运算符), 找到你需要的运算符, 做成变量卡, 下同
02. curried_1 := apply([01]op_someLogic_1, var_exogenous)  # 在逻辑编程器中选择apply, 依次放入刚刚做出的[1]号变量卡, 以及你从别处弄来的外生变量卡（比如物品容器读取器产生的变量之类的）
03. op_otherLogic_1 := op_by_name("otherLogic")
04. op_thirdLogic_1 := op_by_name("thirdLogic")
05. curried_2 := apply([04]op_thirdLogic_1, var_exogenous)
06. func := pipe2([03]op_otherLogic_1, [05]curried_2, [02]curried_1)  # 最终复合运算符, 把这个放在你需要用的地方, 其他变量卡塞进变量卡箱, 就搞定啦
```

It uses pipe, pipe2, apply, apply2..., flip, identity to convert functions to cards.

它的原理就是不断使用一元或二元管道运算符、apply（柯里化）、flip（交换参数）和identity（返回参数本身）这些基本操作来把函数逻辑翻译成变量卡逻辑。