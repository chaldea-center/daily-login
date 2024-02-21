from pathlib import Path

from git import Repo

from fgoapi.schemas.common import Region
from fgoapi.schemas.response import FResponseData

from .login import save_login_result, save_user_entity
from .schemas.data import AccountInfo, AccountStatData


def load_repo_history(
    repo: Repo,
    region: Region,
    userId: int,
    data_folder: Path,
):
    account_dir = f"{region}_{userId}"
    repo_fp: str = f"{account_dir}/login_top/login_top.json"
    stat_fp = data_folder / f"{account_dir}/_stats/data.json"
    account_data = AccountStatData.model_validate_json(stat_fp.read_bytes())
    account_data.info = AccountInfo.model_validate_json(
        (data_folder / account_dir / "info.json").read_bytes()
    )
    commits = sorted(repo.iter_commits(paths=repo_fp), key=lambda x: x.committed_date)
    for commit in commits:
        print("commit", commit.committed_datetime, commit.hexsha[:8])
        content = (commit.tree / repo_fp).data_stream.read().decode()
        resp = FResponseData.model_validate_json(content)
        save_user_entity(account_data, resp)
        save_login_result(account_data.loginResult, resp)

    stat_fp.write_text(account_data.model_dump_json())
