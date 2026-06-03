#!/usr/bin/env python3
"""
Python+ Interpreter — Final Strict Version
Enforces mandatory semicolons at the end of every executable line.
Uses a character-by-character state machine to accurately detect
semicolons outside strings and comments.
"""

import sys


class PythonPlusSyntaxError(Exception):
    """Raised when a required semicolon is missing in Python+ source code."""
    pass


def parse_lines(source: str):
    """
    Parse the entire source code character by character using a state machine.

    Tracks:
    - Whether we are inside a string (single, double, triple-quoted)
    - Bracket nesting depth for implicit line continuation
    - The index of the last executable semicolon per line
      (i.e. a semicolon that appears outside any string or comment)

    Returns a list of dicts, one per line, each containing:
      line_num, original, code_part, comment_part,
      in_string_at_end, bracket_level_at_end, actual_semicolon_idx
    """
    lines = source.splitlines()
    parsed_lines = []

    in_string = None      # current open string delimiter: "'", '"', "'''", or '"""'
    bracket_level = 0     # depth of open brackets: (), [], {}

    for line_num, line in enumerate(lines, start=1):
        code_chars    = []   # characters that belong to executable code
        comment_chars = []   # characters that belong to an inline comment
        in_comment    = False
        skip          = 0    # number of upcoming characters already consumed

        # Index of the last ';' found outside strings/comments in this line.
        # Set to len(code_chars) BEFORE appending ';', so after the loop
        # code_part[actual_semicolon_idx] == ';'.
        last_executable_semicolon_idx = -1

        for idx, c in enumerate(line):
            # --- Skip characters already consumed (e.g. 2nd/3rd char of """) ---
            if skip > 0:
                skip -= 1
                continue

            # --- Inside an inline comment: collect remaining chars as comment ---
            if in_comment:
                comment_chars.append(c)
                continue

            # --- Inside a string literal ---
            if in_string:
                code_chars.append(c)

                # Handle escape sequences (e.g. \", \', \\)
                if c == '\\':
                    if idx + 1 < len(line):
                        code_chars.append(line[idx + 1])
                        skip = 1
                    continue

                # Check for closing triple quote
                if in_string in ("'''", '"""'):
                    if line[idx:idx + 3] == in_string:
                        code_chars.append(line[idx + 1])
                        code_chars.append(line[idx + 2])
                        in_string = None
                        skip = 2
                else:
                    # Check for closing single/double quote
                    if c == in_string:
                        in_string = None
                continue

            # --- Outside strings and comments ---

            # Detect opening triple quote
            if line[idx:idx + 3] in ("'''", '"""'):
                in_string = line[idx:idx + 3]
                code_chars.extend([line[idx], line[idx + 1], line[idx + 2]])
                skip = 2
                continue

            # Detect opening single/double quote
            if c in ("'", '"'):
                in_string = c
                code_chars.append(c)
                continue

            # Detect start of inline comment
            if c == '#':
                in_comment = True
                comment_chars.append(c)
                continue

            # Track bracket nesting for implicit line continuation
            if c in ('(', '[', '{'):
                bracket_level += 1
            elif c in (')', ']', '}'):
                bracket_level = max(0, bracket_level - 1)

            # Record the position of this executable semicolon.
            # We use len(code_chars) BEFORE appending, so the final index
            # in the completed code_part string equals this value.
            if c == ';':
                last_executable_semicolon_idx = len(code_chars)

            code_chars.append(c)

        parsed_lines.append({
            'line_num'              : line_num,
            'original'             : line,
            'code_part'            : "".join(code_chars),
            'comment_part'         : "".join(comment_chars),
            'in_string_at_end'     : in_string,        # None or open delimiter
            'bracket_level_at_end' : bracket_level,    # >0 means line continues
            'actual_semicolon_idx' : last_executable_semicolon_idx
        })

    return parsed_lines


def requires_semicolon(p: dict) -> bool:
    """
    Decide whether a parsed line must end with a semicolon.

    Lines that do NOT require a semicolon:
    - Empty lines or comment-only lines
    - Decorators (@something)
    - Block headers that end with ':' (if, for, def, class, else, try, except...)
    - Explicit line continuations ending with '\'
    - Lines where a multiline string is still open at the end
    - Lines inside an implicit continuation (open bracket not yet closed)
    """
    code_stripped = p['code_part'].strip()

    if not code_stripped:
        return False
    if code_stripped.startswith('@'):
        return False
    if code_stripped.endswith(':'):
        return False
    if code_stripped.endswith('\\'):
        return False
    if p['in_string_at_end'] in ("'''", '"""'):
        return False
    if p['bracket_level_at_end'] > 0:
        return False

    return True


def check_and_strip(source: str, filename: str) -> str:
    """
    Validate semicolon rules and return clean Python source.

    For every line that requires a semicolon:
    - If no executable semicolon is found at the end → record an error.
    - If a valid semicolon is found → remove it so standard Python can run the code.

    Raises PythonPlusSyntaxError (after printing all errors) if any line fails.
    """
    parsed      = parse_lines(source)
    errors      = []
    clean_lines = []

    for p in parsed:
        # Lines exempt from the semicolon rule are passed through unchanged
        if not requires_semicolon(p):
            clean_lines.append(p['original'])
            continue

        semi_idx      = p['actual_semicolon_idx']
        has_valid_semi = False

        if semi_idx != -1:
            # Make sure nothing (except whitespace) follows the semicolon
            # in the code portion — e.g. "x = 1; y = 2" has a mid-line semicolon
            # but the line does not end with one, so it is rejected.
            trailing = p['code_part'][semi_idx + 1:]
            if not trailing or trailing.isspace():
                has_valid_semi = True

        if not has_valid_semi:
            errors.append(
                f"  Line {p['line_num']}: missing semicolon ← {p['original'].rstrip()}"
            )
            clean_lines.append(p['original'])
        else:
            # Strip the semicolon using the exact index recorded during parsing
            clean_code = p['code_part'][:semi_idx] + p['code_part'][semi_idx + 1:]
            clean_lines.append(clean_code + p['comment_part'])

    if errors:
        print(f"\n[Python+] Syntax error in: {filename}")
        print("The following lines are missing a semicolon (;):\n")
        for e in errors:
            print(e)
        print()
        raise PythonPlusSyntaxError()

    return "\n".join(clean_lines)


def run_file(filename: str):
    """Read a .pyp file, validate it, and execute it."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"[Python+] File not found: {filename}")
        sys.exit(1)

    try:
        clean_source = check_and_strip(source, filename)
        exec(compile(clean_source, filename, "exec"), {"__name__": "__main__"})
    except PythonPlusSyntaxError:
        sys.exit(1)
    except Exception as e:
        print(f"\n[Runtime error]: {e}")
        sys.exit(1)


def repl():
    """
    Interactive REPL for Python+.
    Supports multi-line blocks (if/for/def/class) and implicit continuations.
    Executes when the current buffer forms a complete statement.
    """
    print("Python+ REPL — type exit(); to quit")
    print("Remember: every executable line must end with ;\n")
    buffer = []

    while True:
        try:
            prompt = ">>> " if not buffer else "... "
            line   = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if line.strip() == "exit();":
            print("Goodbye!")
            break

        buffer.append(line)
        source = "\n".join(buffer)

        parsed = parse_lines(source)
        if not parsed:
            buffer = []
            continue

        last_line     = parsed[-1]
        code_stripped = last_line['code_part'].strip()

        # The buffer is incomplete if a string/bracket is still open,
        # or if the last line ends with ':' (block header) or '\' (continuation)
        is_incomplete = (
            last_line['in_string_at_end']          or
            last_line['bracket_level_at_end'] > 0  or
            code_stripped.endswith(':')            or
            code_stripped.endswith('\\')
        )

        # Execute when: user enters a blank line, or the statement is complete
        if line.strip() == "" or not is_incomplete:
            if source.strip():
                try:
                    clean = check_and_strip(source, "<repl>")
                    try:
                        # Try eval first to display expression results directly
                        result = eval(compile(clean, "<repl>", "eval"))
                        if result is not None:
                            print(result)
                    except SyntaxError:
                        # Fall back to exec for statements (assignments, loops, etc.)
                        exec(compile(clean, "<repl>", "exec"), {"__name__": "__main__"})
                except PythonPlusSyntaxError:
                    pass   # Error already printed; keep the REPL alive
                except Exception as e:
                    print(f"Error: {e}")
            buffer = []


def main():
    """Entry point registered by pyproject.toml for the 'pythonplusplus' and 'pyp' commands."""
    if len(sys.argv) < 2:
        repl()
    else:
        run_file(sys.argv[1])


if __name__ == "__main__":
    main()

