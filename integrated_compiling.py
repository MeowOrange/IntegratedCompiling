import re
from dataclasses import dataclass


# --- Phase 1: 类型化的AST和占位符 ---

class ASTNode:
    def has_in_dependency(self) -> bool:
        """递归检查此节点或其子节点是否依赖于 'in'"""
        return False


@dataclass(frozen=True)
class Placeholder:
    """一个类型化的占位符，代表一个临时的中间变量"""
    base_name: str
    id: int

    def __repr__(self): return f"P({self.base_name},{self.id})"


class CallNode(ASTNode):
    def __init__(self, op_name, children): self.op_name, self.children = op_name, children

    def __repr__(self): return f"Call('{self.op_name}', {self.children})"

    def has_in_dependency(self) -> bool:
        return any(child.has_in_dependency() for child in self.children)


class VariableNode(ASTNode):
    def __init__(self, name): self.name = name

    def __repr__(self): return f"Var('{self.name}')"

    def has_in_dependency(self) -> bool:
        return self.name == 'in'


class LiteralNode(ASTNode): pass


class StringLiteralNode(LiteralNode):
    def __init__(self, value): self.value = value

    def __repr__(self): return f"Str({self.value!r})"


class NumberLiteralNode(LiteralNode):
    def __init__(self, value): self.value = value

    def __repr__(self): return f"Num({self.value})"


class BooleanLiteralNode(LiteralNode):
    def __init__(self, value): self.value = value

    def __repr__(self): return f"Bool({self.value})"


# --- Phase 2: 增强的解析器 ---

class Parser:
    LITERALS_REGEX = [
        (r'\"(.*?)\"|\'(.*?)\'', lambda m: StringLiteralNode(m.group(1) or m.group(2))),
        (r'\b(true|True|false|False)\b', lambda m: BooleanLiteralNode(m.group(1).lower() == 'true')),
        (r'\b\d+\.\d+\b', lambda m: NumberLiteralNode(float(m.group(0)))),
        (r'\b\d+\b', lambda m: NumberLiteralNode(int(m.group(0)))),
    ]

    def parse(self, code):
        code = code.strip()
        for pattern, factory in self.LITERALS_REGEX:
            if re.fullmatch(pattern, code):
                return factory(re.match(pattern, code))
        if re.fullmatch(r"[\w_]+", code): return VariableNode(code)
        match = re.match(r"([\w_]+)\((.*)\)$", code, re.DOTALL)
        if not match: raise ValueError(f"无效的表达式格式: {code}")
        op_name, args_str = match.groups()
        children = [self.parse(arg) for arg in self._split_args(args_str)] if args_str.strip() else []
        return CallNode(op_name, children)

    def _split_args(self, args_str):
        args, balance, start = [], 0, 0
        for i, char in enumerate(args_str):
            if char == '(':
                balance += 1
            elif char == ')':
                balance -= 1
            elif char == ',' and balance == 0:
                args.append(args_str[start:i].strip());
                start = i + 1
        args.append(args_str[start:].strip())
        return args


# --- Phase 3: 重构的编译器 ---

class Compiler:
    def __init__(self):
        self.steps, self.temp_var_id, self.memo = [], 0, {}

    def new_temp_placeholder(self, base_name="temp"):
        clean_base_name = re.sub(r'[^a-zA-Z0-9_]', '', base_name)
        self.temp_var_id += 1
        return Placeholder(clean_base_name, self.temp_var_id)

    def add_step(self, output_placeholder, operator, inputs, comment=""):
        self.steps.append({"out": output_placeholder, "op": operator, "in": inputs, "comment": comment})
        return output_placeholder

    def get_op_by_name(self, op_name):
        key = f"op_{op_name}"
        if key in self.memo: return self.memo[key]
        placeholder = self.new_temp_placeholder(base_name=f"op_{op_name}")
        self.memo[key] = placeholder
        return self.add_step(placeholder, "op_by_name", [f'"{op_name}"'])

    def compile(self, full_code):
        self.steps, self.temp_var_id, self.memo = [], 0, {}
        full_code = full_code.strip()
        match = re.match(r"(\w+)\s*\(\s*in\s*\)\s*:=\s*(.*)", full_code, re.DOTALL)
        if not match: raise ValueError("代码必须是 'func_name(in) := expression' 的格式")
        func_name, body_code = match.groups()
        ast = Parser().parse(body_code)
        final_op_placeholder = self._compile_to_operator(ast)
        self._render_output(func_name, final_op_placeholder)
        print("--- 编译成功! ---")
        print("--- 逻辑编程器步骤: ---\n")
        for i, step_str in enumerate(self.final_steps, 1): print(f"{i:02d}. {step_str}")
        return self.final_steps

    def _render_output(self, func_name, final_op_placeholder):
        # 1. 垃圾回收
        used_placeholders = {final_op_placeholder}
        for step in reversed(self.steps):
            if step["out"] in used_placeholders:
                for var in step["in"]:
                    if isinstance(var, Placeholder): used_placeholders.add(var)
        filtered_steps = [step for step in self.steps if step["out"] in used_placeholders]

        # 2. 第一次渲染：确定变量名和定义行号
        placeholder_to_name = {}
        placeholder_to_line = {}
        counters = {}
        for i, step in enumerate(filtered_steps, 1):
            out_placeholder = step["out"]
            placeholder_to_line[out_placeholder] = i
            if out_placeholder not in placeholder_to_name:
                base_name = out_placeholder.base_name
                counters[base_name] = counters.get(base_name, 0) + 1
                placeholder_to_name[out_placeholder] = f"{base_name}_{counters[base_name]}"

        # 3. 第二次渲染：格式化最终输出
        self.final_steps = []
        for i, step in enumerate(filtered_steps, 1):
            out_name = placeholder_to_name[step["out"]]
            if step["out"] == final_op_placeholder:
                out_name = func_name
                step["comment"] += "最终复合运算符"

            # 格式化输入参数
            final_inputs_str = []
            for var in step["in"]:
                if isinstance(var, Placeholder):
                    var_name = placeholder_to_name.get(var, repr(var))
                    line_num = placeholder_to_line.get(var, "?")
                    final_inputs_str.append(f"[{line_num:02d}]{var_name}")
                else:  # 静态值或字面量
                    final_inputs_str.append(str(var))

            step_str = f"{out_name} := {step['op']}({', '.join(final_inputs_str)})"
            if step['comment']: step_str += f"  # {step['comment']}"
            self.final_steps.append(step_str)

    # --- 核心编译逻辑（自上而下模式匹配）---

    def _compile_to_operator(self, node: ASTNode) -> Placeholder:
        node_repr = repr(node)
        if node_repr in self.memo: return self.memo[node_repr]

        # 模式1: 节点是 'in' 本身
        if isinstance(node, VariableNode) and node.name == 'in':
            result_op = self.get_op_by_name("identity")

        # 模式2: 节点是包含 'in' 的函数调用
        elif isinstance(node, CallNode) and node.has_in_dependency():
            result_op = self._handle_dynamic_call(node)

        # 其他任何情况都不应该由这个函数处理
        else:
            raise TypeError(f"逻辑错误: _compile_to_operator 不应被用于静态节点 '{node_repr}'")

        self.memo[node_repr] = result_op
        return result_op

    def _handle_dynamic_call(self, node: CallNode) -> Placeholder:
        dynamic_children = [(c, i) for i, c in enumerate(node.children) if c.has_in_dependency()]
        static_children = [(c, i) for i, c in enumerate(node.children) if not c.has_in_dependency()]

        # 步骤1: 柯里化所有静态参数
        op_after_currying = self._curry_statics(node.op_name, node.children, static_children)

        # 步骤2: 根据动态参数数量选择组合策略
        if len(dynamic_children) == 1:
            op_dynamic = self._compile_to_operator(dynamic_children[0][0])
            if op_dynamic == self.get_op_by_name("identity"):
                return op_after_currying
            else:
                return self.add_step(self.new_temp_placeholder("piped"), "pipe", [op_dynamic, op_after_currying])

        elif len(dynamic_children) == 2:
            ops = sorted([(self._compile_to_operator(c), i) for c, i in dynamic_children], key=lambda x: x[1])
            return self.add_step(self.new_temp_placeholder("pipe2"), "pipe2", [ops[0][0], ops[1][0], op_after_currying])

        else:
            raise NotImplementedError(f"函数 '{node.op_name}' 有 {len(dynamic_children)} 个动态参数，超过了 'pipe2' 的支持范围。")

    def _curry_statics(self, op_name, all_children, static_children_info):
        op_after_currying = self.get_op_by_name(op_name)
        pending_args = list(range(len(all_children)))

        for static_child, static_idx in sorted(static_children_info, key=lambda x: x[1]):
            static_value = self._compile_to_value(static_child)
            current_pos = pending_args.index(static_idx)
            op_to_apply_on = op_after_currying
            if current_pos > 0:
                if current_pos > 1: raise NotImplementedError(f"柯里化 '{op_name}' 失败：无法移动超过一个位置的参数。")
                op_to_apply_on = self.add_step(self.new_temp_placeholder("flipped"), "flip", [op_after_currying])
            op_after_currying = self.add_step(self.new_temp_placeholder("curried"), "apply", [op_to_apply_on, static_value])
            pending_args.pop(current_pos)
        return op_after_currying

    def _compile_to_value(self, node: ASTNode):
        node_repr = repr(node) + "_val"
        if node_repr in self.memo: return self.memo[node_repr]

        # 此函数处理的任何节点都不应依赖 'in'
        if node.has_in_dependency():
            raise TypeError(f"逻辑错误: _compile_to_value 不应被用于动态节点 '{node_repr}'")

        # 根据节点类型生成值
        if isinstance(node, VariableNode): return node.name
        if isinstance(node, StringLiteralNode):
            p = self.new_temp_placeholder("str_lit");
            self.add_step(p, "String", [repr(node.value)]);
            self.memo[node_repr] = p;
            return p
        if isinstance(node, NumberLiteralNode):
            val_type = "Integer" if isinstance(node.value, int) else "Double"
            p = self.new_temp_placeholder(val_type.lower());
            self.add_step(p, val_type, [node.value]);
            self.memo[node_repr] = p;
            return p
        if isinstance(node, BooleanLiteralNode):
            p = self.new_temp_placeholder("bool");
            self.add_step(p, "Boolean", [str(node.value)]);
            self.memo[node_repr] = p;
            return p
        if isinstance(node, CallNode):
            arg_values = [self._compile_to_value(c) for c in node.children]
            op_card = self.get_op_by_name(node.op_name)
            arity = len(arg_values)
            if arity > 3: raise NotImplementedError("apply_n 需要列表")
            apply_op_name = {0: "apply0", 1: "apply", 2: "apply2", 3: "apply3"}[arity]
            p = self.new_temp_placeholder(f"val_{node.op_name}");
            self.add_step(p, apply_op_name, [op_card] + arg_values);
            self.memo[node_repr] = p;
            return p

        raise TypeError(f"未知节点类型，无法编译为值: {type(node)}")


# --- 使用示例 ---
code_1 = r"""
valueble_fished(in) := booleanNot(booleanAnd(booleanNot(booleanOr(itemstackIsStackable(in), itemstackIsEnchanted(in))), anyNotEquals(var_zero, itemstackDamage(in))))
"""

Compiler().compile(code_1)

code_2 = r"""
not_enchanted_nor_enchant_book(in) := booleanNot(booleanOr(itemstackIsEnchanted(in), anyEquals("minecraft:enchanted_book", uniquely_namedUniqueName(in))))
"""

Compiler().compile(code_2)
