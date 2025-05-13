import sys
from datetime import datetime, timezone
from pathlib import Path

import git


def main():
    repo = git.Repo(Path(__file__).parent.parent, search_parent_directories=True)
    assert repo.working_tree_dir
    repo_root = Path(repo.working_tree_dir)

    latest_commit = repo.head.commit
    commit_date = latest_commit.committed_datetime.astimezone(timezone.utc)
    current_time = datetime.now(timezone.utc)
    time_diff = current_time - commit_date

    print(f"Last commit info:\ntime: {commit_date.isoformat()}")
    print(f"message: {latest_commit.message.strip()}")
    print(f"elapsed: {time_diff.days} days\n")

    critical_days = 60
    if time_diff.days >= critical_days:
        keepalive_file = repo_root / ".keep-alive"

        timestamp_str = current_time.replace(microsecond=0).isoformat()
        if "+" in timestamp_str:
            timestamp_str = timestamp_str.split("+")[0] + "Z"

        old_content = ""
        if keepalive_file.exists():
            old_content = keepalive_file.read_text(encoding="utf-8").strip()

        keepalive_file.write_text(timestamp_str, encoding="utf-8")

        print(
            f"Updating .keep-alive:\nprevious: {old_content or 'empty'}\ncurrent : {timestamp_str}\n"
        )

        repo.git.add(str(keepalive_file))
        repo.index.commit(f"[keep-alive] {timestamp_str}")

        # origin = repo.remote(name="origin")
        # push_info = origin.push()[0]

        # if push_info.flags & push_info.ERROR:
        #     print("\n[ERROR] push failed")
        # else:
        #     print("\nPush successfully")
    else:
        print(f"\nNo need to commit. Less than {critical_days} days.")


if __name__ == "__main__":
    main()
