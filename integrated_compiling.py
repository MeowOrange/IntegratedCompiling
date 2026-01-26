import re

# --- AST & Parser (无变化) ---
class ASTNode: pass
class CallNode(ASTNode):
    def __init__(self, op_name, children): self.op_name, self._children = op_name, children
    @property
    def children(self): return self._children
    def __repr__(self): return f"Call('{self.op_name}', {self._children})"
class VariableNode(ASTNode):
    def __init__(self, name): self.name = name
    def __repr__(self): return f"Var('{self.name}')"
class StringLiteralNode(ASTNode):
    def __init__(self, value): self.value = value
    def __repr__(self): return f"Str('{self.value}')"

class Parser:
    def parse(self, code):
        code = code.strip()
        if code.startswith('"') and code.endswith('"'): return StringLiteralNode(code[1:-1])
        if re.fullmatch(r"[\w_]+", code): return VariableNode(code)
        match = re.match(r"([\w_]+)\((.*)\)$", code, re.DOTALL)
        if not match: raise ValueError(f"无效的表达式格式: {code}")
        op_name, args_str = match.groups()
        children = [self.parse(arg) for arg in self._split_args(args_str)] if args_str.strip() else []
        return CallNode(op_name, children)
    def _split_args(self, args_str):
        args, balance, start = [], 0, 0
        for i, char in enumerate(args_str):
            if char == '(': balance += 1
            elif char == ')': balance -= 1
            elif char == ',' and balance == 0:
                args.append(args_str[start:i].strip())
                start = i + 1
        args.append(args_str[start:].strip())
        return args

class Compiler:
    # --- 占位符定义 ---
    P_START = "%%P_S%"
    P_MID = "%P_M%"
    P_END = "%P_E%%"
    P_REGEX = re.compile(f"{re.escape(P_START)}(.*?){re.escape(P_MID)}(\\d+){re.escape(P_END)}")

    def __init__(self):
        self.steps, self.temp_var_id, self.memo = [], 0, {}

    def new_temp_placeholder(self, base_name="temp"):
        # 清理 base_name, 移除 . 和其他可能引起问题的字符
        clean_base_name = re.sub(r'[^a-zA-Z0-9_]', '', base_name)
        self.temp_var_id += 1
        return f"{self.P_START}{clean_base_name}{self.P_MID}{self.temp_var_id}{self.P_END}"

    def add_step(self, output_placeholder, operator, inputs, comment=""):
        self.steps.append({ "out": output_placeholder, "op": operator, "in": inputs, "comment": comment })
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
        for i, step_str in enumerate(self.final_steps, 1):
             print(f"{i:02d}. {step_str}")

        return self.final_steps

    def _render_output(self, func_name, final_op_placeholder):
        # 1. 垃圾回收
        used_placeholders = {final_op_placeholder}
        for step in reversed(self.steps):
            if step["out"] in used_placeholders:
                for var in step["in"]:
                    if isinstance(var, str):
                        found_groups = self.P_REGEX.findall(var)
                        used_placeholders.update(f'{self.P_START}{base_name}{self.P_MID}{idx}{self.P_END}' for base_name, idx in found_groups)

        filtered_steps = [step for step in self.steps if step["out"] in used_placeholders]

        # 2. 重新编号并格式化
        self.final_steps = []
        placeholder_to_final_name = {}
        counters = {}

        for step in filtered_steps:
            # 解析占位符以获取基本名称
            out_placeholder = step["out"]
            match = self.P_REGEX.match(out_placeholder)
            base_name = "temp"
            if match:
                base_name = match.group(1)

            # 确定输出变量名
            if out_placeholder not in placeholder_to_final_name:
                counters[base_name] = counters.get(base_name, 0) + 1
                out_name = f"{base_name}_{counters[base_name]}"
                placeholder_to_final_name[out_placeholder] = out_name
            else:
                 out_name = placeholder_to_final_name[out_placeholder]


            # 替换输入中的占位符
            final_inputs = []
            for var in step["in"]:
                if isinstance(var, str):
                    # 使用一个函数来处理替换，避免循环套循环的问题
                    def replacer(match_obj):
                        p_to_replace = match_obj.group(0)
                        return placeholder_to_final_name.get(p_to_replace, p_to_replace)
                    var = self.P_REGEX.sub(replacer, var)
                final_inputs.append(var)

            # 格式化最终的字符串
            if step["out"] == final_op_placeholder:
                out_name = func_name
                step["comment"] += "最终复合运算符"

            step_str = f"{out_name} := {step['op']}({', '.join(map(str, final_inputs))})"
            if step['comment']: step_str += f"  # {step['comment']}"
            self.final_steps.append(step_str)

    def _compile_to_operator(self, node):
        node_repr = repr(node)
        if node_repr in self.memo: return self.memo[node_repr]

        result_op = None
        if isinstance(node, VariableNode) and node.name == 'in':
            result_op = self.get_op_by_name("identity")

        elif isinstance(node, (VariableNode, StringLiteralNode)):
            const_val_card = self._compile_to_value(node)
            const_op = self.get_op_by_name("constant")
            result_op = self.new_temp_placeholder(f"op_const_{const_val_card}")
            self.add_step(result_op, "apply", [const_op, const_val_card], f"创建始终返回 '{const_val_card}' 的运算符")

        elif isinstance(node, CallNode):
            dynamic_children_info = [(child, i) for i, child in enumerate(node.children) if 'in' in repr(child)]
            static_children_info = [(child, i) for i, child in enumerate(node.children) if not 'in' in repr(child)]

            base_op = self.get_op_by_name(node.op_name)
            op_after_currying = base_op

            pending_args = list(range(len(node.children)))

            for static_child, static_idx in sorted(static_children_info, key=lambda x: x[1]):
                static_value = self._compile_to_value(static_child)
                current_pos = pending_args.index(static_idx)
                op_to_apply_on = op_after_currying

                if current_pos > 0:
                    if current_pos > 1:
                        raise NotImplementedError(f"柯里化 '{node.op_name}' 失败：无法移动超过一个位置的参数。")
                    op_to_apply_on = self.add_step(self.new_temp_placeholder("flipped"), "flip", [op_after_currying])

                comment = f"柯里化 '{node.op_name}': 应用参数 {static_idx} ('{static_value}')"
                op_after_currying = self.add_step(self.new_temp_placeholder("curried"), "apply", [op_to_apply_on, static_value], comment)
                pending_args.pop(current_pos)

            if not dynamic_children_info:
                const_op = self.get_op_by_name("constant")
                const_val = self._compile_to_value(node)
                result_op = self.add_step(self.new_temp_placeholder("op_const"), "apply", [const_op, const_val])

            elif len(dynamic_children_info) == 1:
                op_dynamic = self._compile_to_operator(dynamic_children_info[0][0])
                if op_dynamic == self.get_op_by_name("identity"):
                    result_op = op_after_currying
                else:
                    result_op = self.add_step(self.new_temp_placeholder("piped"), "pipe", [op_dynamic, op_after_currying])

            elif len(dynamic_children_info) == 2:
                dynamic_ops = sorted([(self._compile_to_operator(child), idx) for child, idx in dynamic_children_info], key=lambda x: x[1])
                op_dynamic1 = dynamic_ops[0][0]
                op_dynamic2 = dynamic_ops[1][0]
                result_op = self.add_step(self.new_temp_placeholder("pipe2"), "pipe2", [op_dynamic1, op_dynamic2, op_after_currying])

            else:
                 raise NotImplementedError(f"函数 '{node.op_name}' 有 {len(dynamic_children_info)} 个动态参数，超过了 'pipe2' 的支持范围。")
        else:
            raise TypeError(f"未知的AST节点类型: {type(node)}")

        self.memo[node_repr] = result_op
        return result_op

    def _compile_to_value(self, node):
        node_repr = repr(node) + "_val"
        if node_repr in self.memo: return self.memo[node_repr]
        result_val = None
        if isinstance(node, VariableNode):
            result_val = node.name
        elif isinstance(node, StringLiteralNode):
            result_val = self.new_temp_placeholder("str_lit")
            self.add_step(result_val, "String", [f'"{node.value}"'], "创建静态字符串卡")
        elif isinstance(node, CallNode):
            arg_values = [self._compile_to_value(child) for child in node.children]
            op_card = self.get_op_by_name(node.op_name)
            arity = len(arg_values)
            if arity > 3: raise NotImplementedError("apply_n 需要列表")
            apply_op_name = {0: "apply0", 1: "apply", 2: "apply2", 3: "apply3"}[arity]
            inputs = [op_card] + arg_values
            result_val = self.new_temp_placeholder(f"{node.op_name}_val")
            self.add_step(result_val, apply_op_name, inputs)
        else:
            raise TypeError(f"未知节点类型，无法编译为值: {type(node)}")
        self.memo[node_repr] = result_val
        return result_val

# --- 使用示例 ---
code_1 = r"""
func(in) := booleanOr(itemstackIsEnchanted(in), itemstackIsStackable(in))
"""

# 终极测试用例
code_3 = r"""
ultimate_test(in) := listGetOrDefault(
                                  in,                        
                                  var_default_idx,           
                                  itemstackSize(             
                                      heldItem(in)
                                  )
                               )
"""

print("--- 编译示例 1 (优雅占位符版) ---")
Compiler().compile(code_1)

print("\n\n--- 编译示例 3 (终极测试) ---")
Compiler().compile(code_3)