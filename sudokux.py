#!/usr/bin/env python3
"""sudokux — X 数独（对角线数独）生成器与回溯求解器。

规则：9x9 标准数独约束（行/列/3x3 宫 1-9 不重复），外加两条主对角线
(r==c 与 r+c==8) 也必须 1-9 不重复。

纯标准库：argparse / random / sys。
"""

import argparse
import random
import sys

N = 9
DIGITS = tuple(range(1, 10))


class _BudgetExceeded(Exception):
    """搜索节点数超出预算。"""


def candidates(grid, r, c):
    """空格 (r, c) 的候选数字（含对角线约束）。"""
    used = set(grid[r])
    used.update(grid[i][c] for i in range(N))
    br, bc = 3 * (r // 3), 3 * (c // 3)
    for i in range(br, br + 3):
        for j in range(bc, bc + 3):
            used.add(grid[i][j])
    if r == c:
        used.update(grid[i][i] for i in range(N))
    if r + c == N - 1:
        used.update(grid[i][N - 1 - i] for i in range(N))
    return [d for d in DIGITS if d not in used]


def is_consistent(grid):
    """给定数之间无冲突（行/列/宫/两条对角线的非零数不重复）。"""
    for i in range(N):
        for vals in (
            [grid[i][c] for c in range(N) if grid[i][c]],
            [grid[r][i] for r in range(N) if grid[r][i]],
        ):
            if len(set(vals)) != len(vals):
                return False
        br, bc = 3 * (i // 3), 3 * (i % 3)
        vals = [grid[r][c] for r in range(br, br + 3)
                for c in range(bc, bc + 3) if grid[r][c]]
        if len(set(vals)) != len(vals):
            return False
    d1 = [grid[i][i] for i in range(N) if grid[i][i]]
    if len(set(d1)) != len(d1):
        return False
    d2 = [grid[i][N - 1 - i] for i in range(N) if grid[i][N - 1 - i]]
    if len(set(d2)) != len(d2):
        return False
    return True


def count_solutions(grid, limit=2, rng=None, budget=100_000):
    """数解的个数，上限为 limit。

    返回 (count, first_solution)。count == -1 表示搜索超出 budget 未完成；
    此时 first_solution 为 None。
    rng 非 None 时打乱候选顺序（用于生成随机完整解）。
    """
    g = [row[:] for row in grid]
    if not is_consistent(g):
        return 0, None
    sols = []
    nodes = [0]

    def rec():
        nodes[0] += 1
        if nodes[0] > budget:
            raise _BudgetExceeded()
        # MRV：选候选最少的空格
        best = None
        best_c = None
        for r in range(N):
            for c in range(N):
                if g[r][c] == 0:
                    cc = candidates(g, r, c)
                    if not cc:
                        return False
                    if best is None or len(cc) < len(best_c):
                        best, best_c = (r, c), cc
                        if len(cc) == 1:
                            break
            if best_c is not None and len(best_c) == 1:
                break
        if best is None:
            sols.append([row[:] for row in g])
            return len(sols) >= limit
        r, c = best
        order = list(best_c)
        if rng is not None:
            rng.shuffle(order)
        for d in order:
            g[r][c] = d
            done = rec()
            g[r][c] = 0
            if done:
                return True
        return False

    try:
        rec()
    except _BudgetExceeded:
        return -1, None
    if not sols:
        return 0, None
    return len(sols), sols[0]


def solve(grid, budget=1_000_000):
    """求解，返回第一个解；无解返回 None；超预算抛 _BudgetExceeded。"""
    cnt, sol = count_solutions(grid, limit=1, budget=budget)
    if cnt == -1:
        raise _BudgetExceeded()
    return sol


def check_solution(grid, givens=None):
    """独立验证器：行/列/宫/两条对角线均为 1-9，且与 givens 一致。"""
    want = set(DIGITS)
    for i in range(N):
        if set(grid[i]) != want:
            return False
        if {grid[r][i] for r in range(N)} != want:
            return False
        br, bc = 3 * (i // 3), 3 * (i % 3)
        if {grid[r][c] for r in range(br, br + 3)
                for c in range(bc, bc + 3)} != want:
            return False
    if {grid[i][i] for i in range(N)} != want:
        return False
    if {grid[i][N - 1 - i] for i in range(N)} != want:
        return False
    if givens is not None:
        for r in range(N):
            for c in range(N):
                if givens[r][c] != 0 and givens[r][c] != grid[r][c]:
                    return False
    return True


def full_solution(seed=None):
    """生成一个随机的完整 X 数独解。seed 可为 int 或 random.Random。"""
    rng = seed if isinstance(seed, random.Random) else random.Random(seed)
    cnt, sol = count_solutions([[0] * N for _ in range(N)],
                               limit=1, rng=rng, budget=10_000_000)
    if cnt != 1:
        raise RuntimeError("无法生成完整数独解")
    return sol


def generate(seed=None, givens=30, budget=100_000):
    """生成谜题：随机完整解 → 逐格挖空，每次挖空后验证仍唯一解。

    返回 (puzzle, solution)。保守策略：无法在 budget 内证明唯一
    （含超预算）则恢复该格，所以实际 givens 可能多于目标。
    """
    rng = random.Random(seed)
    sol = full_solution(rng)
    puzzle = [row[:] for row in sol]
    cells = [(r, c) for r in range(N) for c in range(N)]
    rng.shuffle(cells)
    target_remove = N * N - givens
    removed = 0
    for r, c in cells:
        if removed >= target_remove:
            break
        backup = puzzle[r][c]
        puzzle[r][c] = 0
        cnt, _ = count_solutions(puzzle, limit=2, budget=budget)
        if cnt == 1:
            removed += 1
        else:
            puzzle[r][c] = backup  # 0 解（理论上不会）/ 多解 / 超预算都恢复
    return puzzle, sol


def parse_puzzle(text):
    """解析 9 行文本：1-9 为给定数，'.' 或 '0' 为空格。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) != N:
        raise ValueError(f"需要 {N} 行，实际 {len(lines)} 行")
    grid = []
    for i, ln in enumerate(lines):
        if len(ln) != N:
            raise ValueError(f"第 {i + 1} 行长度应为 {N}")
        row = []
        for ch in ln:
            if ch in ".0":
                row.append(0)
            elif ch in "123456789":
                row.append(int(ch))
            else:
                raise ValueError(f"第 {i + 1} 行非法字符 {ch!r}")
        grid.append(row)
    return grid


def render(grid, givens=None):
    """ASCII 渲染；givens 非 None 时空格显示为点、给定数加粗感用 [] 标出。"""
    out = []
    for r in range(N):
        cells = []
        for c in range(N):
            v = grid[r][c]
            if v == 0:
                cells.append("·")
            elif givens is not None and givens[r][c] == 0:
                cells.append(str(v))
            else:
                cells.append(str(v))
        line = " ".join(cells[0:3]) + " │ " + " ".join(cells[3:6]) \
            + " │ " + " ".join(cells[6:9])
        out.append(line)
        if r in (2, 5):
            out.append("──────┼───────┼──────")
    return "\n".join(out)


# ---- 自检 ----

# 固定测试用谜题（seed=7, givens=35 生成；解已用 check_solution 独立验证，
# 且求解器能恢复出唯一解 —— 回归测试用）
_TEST_PUZZLE = [
    [0, 0, 4, 0, 0, 7, 0, 9, 8],
    [0, 7, 6, 0, 8, 9, 4, 0, 5],
    [1, 0, 0, 5, 0, 0, 0, 7, 0],
    [5, 6, 0, 0, 9, 0, 0, 8, 2],
    [4, 0, 0, 2, 0, 0, 0, 0, 7],
    [8, 0, 3, 0, 5, 0, 0, 0, 0],
    [0, 1, 5, 9, 0, 4, 8, 0, 0],
    [6, 0, 0, 0, 0, 3, 0, 0, 9],
    [0, 3, 0, 0, 7, 5, 0, 0, 0],
]

# （固定谜题的解不硬编码：自检时用 check_solution 独立验证求解器输出）


def _selftest():
    passed, failed = 0, 0

    def ok(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [通过] {name}")
        else:
            failed += 1
            print(f"  [失败] {name}")

    # 1. 固定谜题：唯一解，求解器恢复的解必须合法且符合给定数
    cnt, _ = count_solutions(_TEST_PUZZLE, limit=2)
    ok("固定谜题唯一解", cnt == 1)
    sol = solve(_TEST_PUZZLE)
    ok("固定谜题有解", sol is not None)
    ok("固定谜题的解合法（含对角线）",
       sol is not None and check_solution(sol, _TEST_PUZZLE))

    # 2. 10 个种子生成：全部可解，解合法且对角线有效
    all_ok = True
    for seed in range(10):
        puzzle, _ = generate(seed=seed, givens=30)
        s = solve(puzzle)
        if s is None or not check_solution(s, puzzle):
            all_ok = False
            print(f"    seed={seed} 求解失败")
            break
        ng = sum(1 for r in range(N) for c in range(N) if puzzle[r][c] != 0)
        if ng < 30:
            all_ok = False
            print(f"    seed={seed} 给定数 {ng} < 30")
            break
    ok("10 种子生成谜题全部可解且合法", all_ok)

    # 3. 矛盾谜题无解
    bad = [[5] * N for _ in range(N)]
    cnt, _ = count_solutions(bad, limit=1)
    ok("矛盾谜题返回无解", cnt == 0)

    # 4. 文本解析往返
    p, _ = generate(seed=123, givens=32)
    text = "\n".join("".join(str(v) if v else "." for v in row) for row in p)
    ok("文本格式解析往返一致", parse_puzzle(text) == p)

    print(f"自检结果：{passed} 通过，{failed} 失败")
    return failed == 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="sudokux",
        description="X 数独（对角线数独）生成器与求解器：行/列/宫/两条对角线均为 1-9。",
    )
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--givens", type=int, default=30, help="目标给定数（默认 30）")
    ap.add_argument("--solution", action="store_true", help="同时打印答案")
    ap.add_argument("--solve", nargs="?", const="-", metavar="FILE",
                    help="求解谜题：从文件或 stdin 读入 9 行文本")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检")
    args = ap.parse_args(argv)

    if args.selftest:
        sys.exit(0 if _selftest() else 1)

    if args.solve is not None:
        if args.solve == "-":
            text = sys.stdin.read()
        else:
            with open(args.solve, encoding="utf-8") as f:
                text = f.read()
        try:
            puzzle = parse_puzzle(text)
        except ValueError as e:
            print(f"输入错误：{e}", file=sys.stderr)
            sys.exit(2)
        try:
            sol = solve(puzzle)
        except _BudgetExceeded:
            print("搜索超出预算，未完成。", file=sys.stderr)
            sys.exit(3)
        if sol is None:
            print("无解。")
            sys.exit(1)
        print(render(sol))
        return

    if not (17 <= args.givens <= 81):
        print("给定数应在 17～81 之间。", file=sys.stderr)
        sys.exit(2)
    puzzle, sol = generate(seed=args.seed, givens=args.givens)
    ng = sum(1 for r in range(N) for c in range(N) if puzzle[r][c] != 0)
    print(f"X 数独谜题（给定 {ng} 格，seed={args.seed}）：\n")
    print(render(puzzle))
    if args.solution:
        print("\n答案：\n")
        print(render(sol))


if __name__ == "__main__":
    main()
