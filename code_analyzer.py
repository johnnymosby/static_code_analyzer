import sys
import os
import re
import ast
from collections import defaultdict


def open_file_safely(pathname):
    try:
        file = open(pathname, "r")
        return file
    except FileNotFoundError:
        print("File not found:", pathname)
        exit(1)
    except Exception as e:
        print("An error occurred:", e)
        exit(1)


class TreeTraverser(ast.NodeVisitor):
    def __init__(self):
        self.nodes_for_analysis = {
            "args": defaultdict(list),
            "variables": defaultdict(list),
            "default_args": defaultdict(list)
        }

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.nodes_for_analysis["variables"][node.lineno].append(node.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for arg in node.args.args:
            self.nodes_for_analysis["args"][node.lineno].append(arg.arg)
        for arg in node.args.defaults:
            self.nodes_for_analysis["default_args"][node.lineno].append(isinstance(arg, ast.Constant))
        self.generic_visit(node)

    def get_args(self, id_line):
        return self.nodes_for_analysis["args"][id_line]

    def get_variables(self, id_line):
        return self.nodes_for_analysis["variables"][id_line]

    def get_default_args(self, id_line):
        for arg_name, is_arg_default in zip(self.nodes_for_analysis["args"][id_line],
                                            self.nodes_for_analysis["default_args"][id_line]):
            if not is_arg_default:
                return arg_name
            else:
                return ""


class Analyzer:
    def __init__(self, pathname):
        self.pathname = pathname
        self.file = open_file_safely(pathname)
        self.lines = self.file.read().split('\n')
        self.n_lines = len(self.lines)
        self.issues = list()
        self.code_message = ["S000 Not existent issue",
                             "S001 Too long",
                             "S002 Indentation is not a multiple of four",
                             "S003 Unnecessary semicolon",
                             "S004 At least two spaces required before inline comments",
                             "S005 TODO found",
                             "S006 More than two blank lines used before this line"]
        self.n_blank_lines = 0
        self.file.seek(0)
        self.tree = ast.parse(self.file.read())
        self.tree_traverser = TreeTraverser()
        self.tree_traverser.visit(self.tree)

    def construct_issue(self, id_line, id_issue):
        return f"{self.pathname}: Line {id_line}: {self.code_message[id_issue]}"

    def add_issue(self, id_line, id_issue):
        self.issues.append({'id_line': id_line,
                            'id_issue': id_issue,
                            'issue': self.construct_issue(id_line, id_issue)})

    def check_s001(self, id_line, line):
        if len(line) > 79:
            self.add_issue(id_line, 1)

    def check_s002(self, id_line, line):
        if len(line.strip()) == 0:
            pass
        elif (len(line) - len(line.lstrip())) % 4 != 0:
            self.add_issue(id_line, 2)

    def check_s003(self, id_line, line):
        i = 0
        while i < len(line):
            if line[i] in ('\'', '\"'):
                character = line[i]
                i += 1
                while i < len(line) and line[i] != character:
                    i += 1
                if i < len(line):
                    i += 1
            elif line[i] == '#':
                break
            elif line[i] == ';':
                self.add_issue(id_line, 3)
                break
            else:
                i += 1

    def check_s004(self, id_line, line):
        if line.find('#') > 2 and (line[line.find('#') - 1] != ' '
                                   or line[line.find('#') - 2] != ' '):
            self.add_issue(id_line, 4)

    def check_s005(self, id_line, line):
        if line.lower().find('# todo') >= 0:
            self.add_issue(id_line, 5)
            return

    def check_s006(self, id_line):
        if self.n_blank_lines > 2:
            self.add_issue(id_line, 6)
        self.n_blank_lines = 0

    def check_s007(self, id_line, line):
        if result := re.match(r"^(\s*(?:def|class) ( )+)", line):
            classname = 'def' if 'def' in result.group(0) else 'class'
            issue = f"{self.pathname}: Line {id_line}: S007 Too many spaces after {classname}"
            self.issues.append({'id_line': id_line,
                                'id_issue': 7,
                                'issue': issue})

    def check_s008(self, id_line, line):
        if result := re.match(r"^(\s*class (?P<word>\w+))", line):
            if not re.match(r"(?:[A-Z][a-z\d]+)+", result["word"]):
                issue = f"{self.pathname}: Line {id_line}: S008 Class name {result['word']} should be written in CamelCase"
                self.issues.append({'id_line': id_line,
                                    'id_issue': 8,
                                    'issue': issue})

    def check_s009(self, id_line, line):
        if result := re.match(r"^(\s*def (?P<word>\w+))", line):
            if not re.match(r"[a-z_]+", result["word"]):
                issue = f"{self.pathname}: Line {id_line}: S009 Function name {result['word']} should be written in snake_case"
                self.issues.append({'id_line': id_line,
                                    'id_issue': 9,
                                    'issue': issue})

    def check_s010(self, id_line):
        for arg in self.tree_traverser.get_args(id_line):
            if not re.match(r"[a-z_]+", arg):
                issue = f"{self.pathname}: Line {id_line}: S010 Argument name {arg} should be written in snake_case"
                self.issues.append({'id_line': id_line,
                                    'id_issue': 10,
                                    'issue': issue})
                break

    def check_s011(self, id_line):
        for var in self.tree_traverser.get_variables(id_line):
            if not re.match(r"[a-z_]+", var):
                issue = f"{self.pathname}: Line {id_line}: S011 Variable {var} should be written in snake_case"
                self.issues.append({'id_line': id_line,
                                    'id_issue': 11,
                                    'issue': issue})
            break

    def check_s012(self, id_line):
        if self.tree_traverser.get_default_args(id_line):
            issue = f"{self.pathname}: Line {id_line}: S012 The default argument value is mutable"
            self.issues.append({'id_line': id_line,
                                'id_issue': 12,
                                'issue': issue})

    def analyze(self):
        self.file.seek(0)
        for id_line, line in enumerate(self.file, start=1):
            if line == "\n":
                self.n_blank_lines = self.n_blank_lines + 1
                continue
            self.check_s001(id_line, line)
            self.check_s002(id_line, line)
            self.check_s003(id_line, line)
            self.check_s004(id_line, line)
            self.check_s005(id_line, line)
            self.check_s006(id_line)
            self.check_s007(id_line, line)
            self.check_s008(id_line, line)
            self.check_s009(id_line, line)
            self.check_s010(id_line)
            self.check_s011(id_line)
            self.check_s012(id_line)

    def print_issues(self):
        sorted_data = sorted(self.issues, key=lambda item: (item['id_line'], item['id_issue']))
        for issue in sorted_data:
            print(issue['issue'])


def main():
    if len(sys.argv) != 2:
        print("You must provide the program one argument: file or directory")
        exit(0)
    pathname = sys.argv[1]
    if os.path.isfile(pathname):
        report = Analyzer(pathname)
        report.analyze()
        report.print_issues()
    else:
        pathnames = [root + os.sep + name
                     for root, dirs, files in os.walk(pathname)
                     for name in files
                     if name.endswith(".py")]
        pathnames.sort()
        for pathname in pathnames:
            report = Analyzer(pathname)
            report.analyze()
            report.print_issues()


if __name__ == "__main__":
    main()
