"""Terminal front end.

    uv run python -m tutor                      # pick from the list
    uv run python -m tutor lemonade-more-sugar  # a word problem
    uv run python -m tutor compare-fractions:1  # a question's first example
    uv run python -m tutor --list
"""

import sys
import textwrap

from .session import COMMANDS, WordProblemSession, catalog


def say(feedbacks):
    for f in feedbacks:
        mark = {"correct": "", "slip": "  ✎ ", "on_track": "  … ", "trap": "  ✗ ", "unknown": "  ? ", "hint": "  ➜ ",
                "method": "  ◆ ", "done": "  ★ ", "error": "  ! ", "info": "  "}[f.kind]
        print(textwrap.indent(f.message, "  ") if f.kind == "correct" else mark + f.message.replace("\n", "\n    "))


def run(session, inputs=None):
    """Run a session; with `inputs` (a list of lines) it runs unattended and echoes them, for scripts and tests."""
    feed = iter(inputs) if inputs is not None else None
    print()
    print(session.intro() if hasattr(session, "intro") else session.title())
    say(getattr(session, "pending", []))
    print(f"({COMMANDS})")
    while session.phase != "done":
        print("\n" + session.prompt())
        if feed is not None:
            line = next(feed, None)
            if line is None:
                print("(script ended)")
                return session
            print(f"> {line}")
        else:
            try:
                line = input("> ")
            except EOFError:
                return session
        cmd = line.strip().lower()
        if cmd in ("quit", "exit", "q"):
            return session
        if cmd == "hint":
            say(session.hint())
        elif cmd == "where":
            say(session.where())
        elif cmd == "done":
            say(session.done_command() if isinstance(session, WordProblemSession) else session.finish_steps())
        elif cmd in ("help", "?"):
            print(COMMANDS)
        else:
            say(session.submit(line))
    return session


def main(argv):
    items = catalog()
    if "--list" in argv:
        for key, title, _ in items:
            print(f"{key:24s} {title}")
        return
    keys = [a for a in argv if not a.startswith("-")]
    if keys:
        match = [it for it in items if it[0] == keys[0]]
        if not match:
            sys.exit(f"No item {keys[0]!r}; try --list.")
        run(match[0][2]())
        return
    for i, (key, title, _) in enumerate(items, 1):
        print(f"[{i:2d}] {title}")
    choice = input("Pick a number: ").strip()
    run(items[int(choice) - 1][2]())


if __name__ == "__main__":
    main(sys.argv[1:])
