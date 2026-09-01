"""LiveBench's own scoring functions, copied verbatim (not reimplemented) from
livebench/process_results/reasoning/{web_of_lies_v2,spatial,zebra_puzzle}/utils.py
and livebench/process_results/util.py in the LiveBench-main repo. Used as-is
so scoring fidelity matches the real benchmark exactly.

Only the three tasks with public ground truth in the livebench/reasoning
HuggingFace dataset are covered here: web_of_lies_v2, spatial, zebra_puzzle.
"""

import itertools
import re
from typing import Optional


# --- livebench/process_results/util.py ---
def last_boxed_only_string(string: str) -> Optional[str]:
    idx = string.rfind("\\boxed")
    if "\\boxed " in string:
        return "\\boxed " + string.split("\\boxed ")[-1].split("$")[0]
    if idx < 0:
        idx = string.rfind("\\fbox")
        if idx < 0:
            return None
    i = idx
    right_brace_idx = None
    num_left_braces_open = 0
    while i < len(string):
        if string[i] == "{":
            num_left_braces_open += 1
        if string[i] == "}":
            num_left_braces_open -= 1
            if num_left_braces_open == 0:
                right_brace_idx = i
                break
        i += 1
    if right_brace_idx is None:
        return None
    return string[idx : right_brace_idx + 1].replace("$", "").replace("fbox", "boxed")


def remove_boxed(s: str) -> str:
    if "\\boxed " in s:
        left = "\\boxed "
        assert s[: len(left)] == left
        return s[len(left):]
    left = "\\boxed{"
    assert s[: len(left)] == left
    assert s[-1] == "}"
    return s[len(left):-1]


# --- livebench/process_results/reasoning/web_of_lies_v2/utils.py ---
def web_of_lies_process_results(ground_truth: str, llm_answer: str, debug=False) -> float:
    score = 0
    parsed_answer = None

    solution_matches = re.findall(r'<solution>(.*?)</solution>', llm_answer)
    if len(solution_matches) == 0:
        solution_matches = re.findall(r'</solution>(.*?)</solution>', llm_answer)
    if len(solution_matches) > 0:
        parsed_answer = solution_matches[-1]

    bold_words = re.findall(r'\*\*(.*?)\*\*', llm_answer)
    if parsed_answer is None and bold_words:
        bold_words = [word.lower().strip().replace(',', '').replace('.', '')[0:max(len(word), 3)]
                      for match in bold_words for word in match.split()]
        parsed_answer = []
        i = len(bold_words) - 1
        while i >= 0 and len(parsed_answer) < 3:
            if bold_words[i] in ["yes", "no", "unknown"]:
                parsed_answer = [bold_words[i]] + parsed_answer
            i -= 1
        parsed_answer = ", ".join(parsed_answer) if parsed_answer else None

    if parsed_answer is None or parsed_answer.strip() == '':
        llm_answer2 = llm_answer.replace("\\\\boxed{\\\\textbf{", "\\\\boxed{")
        llm_answer2 = llm_answer2.replace("\\\\fbox{", "\\\\boxed{")
        llm_answer2 = llm_answer2.replace("\\textbf{", "\\boxed{")
        last_boxed = last_boxed_only_string(llm_answer2)
        if last_boxed:
            parsed_answer = remove_boxed(last_boxed)

    if parsed_answer is None:
        combs = itertools.product(['yes', 'no', 'unknown'], repeat=3)
        final_comb = None
        final_comb_index = -1
        for comb in combs:
            index = llm_answer.lower().find(', '.join(comb))
            if index != -1 and index > final_comb_index:
                final_comb = comb
                final_comb_index = index
        if final_comb is not None:
            parsed_answer = ', '.join(final_comb)

    if parsed_answer and parsed_answer == ground_truth.lower():
        score = 1
    if (parsed_answer
            and parsed_answer.count("yes") + parsed_answer.count("no") + parsed_answer.count("unknown") == 3
            and ground_truth.lower() in parsed_answer):
        score = 1

    return float(score)


# --- livebench/process_results/reasoning/spatial/utils.py ---
def spatial_process_results(ground_truth: str, llm_answer: str, debug=False) -> float:
    if llm_answer == ground_truth:
        return 1.0

    word_to_number = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14', 'fifteen': '15',
        'sixteen': '16', 'seventeen': '17', 'eighteen': '18', 'nineteen': '19', 'twenty': '20'
    }

    bold_words = re.findall(r'\*\*([^\*]+)\*\*', llm_answer)
    score = 0

    words_to_check = []
    for i in range(3):
        if bold_words and len(bold_words) > i:
            words_to_check.append(bold_words[-i - 1].strip().lower())

    for word in words_to_check:
        if word == ground_truth.strip().lower():
            score = 1
        if word in word_to_number and word_to_number[word] == ground_truth.strip().lower():
            score = 1
        for answer in ["tetrahedra", "tetrahedron", "triangle", "square"]:
            if ground_truth.strip().lower() == answer and answer in word and len(word) < (2 * len(answer) + 5):
                score = 1

    if score == 0:
        llm_answer2 = llm_answer.replace("\\\\fbox{", "\\\\boxed{")
        last_boxed = last_boxed_only_string(llm_answer2)
        if last_boxed:
            parsed_answer = remove_boxed(last_boxed)
            parsed_answer = parsed_answer.replace("\\textbf{", "")
            parsed_answer = parsed_answer.replace("\\mathbf{", "")
            parsed_answer = parsed_answer.replace("\\text{", "")
            parsed_answer = parsed_answer.replace("}", "")
            if parsed_answer == ground_truth:
                score = 1

    return float(score)


# --- livebench/process_results/reasoning/zebra_puzzle/utils.py ---
def zebra_puzzle_process_results_old(ground_truth: str, llm_answer: str, debug=False) -> float:
    number_to_word = {
        '1': 'one', '2': 'two', '3': 'three', '4': 'four',
        '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
    }
    bold_words = re.findall(r'\*\*\*(\w+)\*\*\*', llm_answer)
    score = 0
    if bold_words:
        if (bold_words[-1].lower() == ground_truth.lower() or
                (bold_words[-1] in number_to_word and number_to_word[bold_words[-1]].lower() == ground_truth.lower())
                or bold_words[-1].lower() + ' movies' == ground_truth.lower()):
            score = 1
    else:
        words = re.findall(r'\b\w+\b', llm_answer)
        last_word = words[-1] if words else ''
        if (last_word.lower() == ground_truth.lower() or
                (last_word in number_to_word and number_to_word[last_word].lower() == ground_truth.lower())
                or last_word.lower() + ' movies' == ground_truth.lower()):
            score = 1
    return float(score)


def zebra_puzzle_process_results(ground_truth: str, llm_answer: str, debug=False) -> float:
    word_to_num = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
    }

    ground_truth_list = ground_truth.split(',')

    solution_matches = re.findall(r'<solution>(.*?)</solution>', llm_answer)
    if len(solution_matches) == 0:
        solution_matches = re.findall(r'</solution>(.*?)</solution>', llm_answer)

    if len(solution_matches) == 0:
        llm_answer2 = llm_answer.replace("\\\\fbox{", "\\\\boxed{")
        last_boxed = last_boxed_only_string(llm_answer2)
        if last_boxed:
            boxed_removed = remove_boxed(last_boxed)
            boxed_removed = boxed_removed.replace("\\text{", "").replace("}", "").replace('\\', '')
            solution_matches.append(boxed_removed)

    if len(solution_matches) == 0:
        last_line = llm_answer.strip().split('\n')[-1]
        if last_line.count(',') == len(ground_truth_list) - 1:
            solution_matches.append(last_line)

    if len(solution_matches) == 0:
        return 0.0

    if len(solution_matches) > 1:
        all_solution_text = []
        for match in solution_matches:
            all_solution_text += match.split(',')
        solution_text = all_solution_text[-len(ground_truth_list):]
    else:
        solution_text = solution_matches[-1].split(',')

    num_correct = 0
    total = len(ground_truth_list)
    for i in range(total):
        gt_word = ground_truth_list[i].strip().lower().replace('-', ' ')
        if i >= len(solution_text):
            continue
        llm_word = solution_text[i].strip().lower().replace('-', ' ').replace('position', '')
        if gt_word == llm_word or gt_word in llm_word:
            num_correct += 1

    return ((num_correct == total) + num_correct / total) / 2


def get_zebra_puzzle_evaluator(release_date: str):
    if release_date < '2024-11-25':
        return zebra_puzzle_process_results_old
    return zebra_puzzle_process_results


SCORERS = {
    "web_of_lies_v2": lambda gt, ans, release_date: web_of_lies_process_results(gt, ans),
    "spatial": lambda gt, ans, release_date: spatial_process_results(gt, ans),
    "zebra_puzzle": lambda gt, ans, release_date: get_zebra_puzzle_evaluator(release_date)(gt, ans),
}
