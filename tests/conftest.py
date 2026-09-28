"""pytest共通設定。

.env に DB_BACKEND=sqlite や mysql が書かれていても、自動テストは常に
インメモリ（memory）モードで動くようにする。
（load_dotenv() は既に設定済みの環境変数を上書きしないため、
 app を import する前にここで設定しておけば .env より優先される。）

SQLite実装そのもののテストは tests/test_sqlite_store.py で、
一時ファイルのDBを使って別途行っている。
"""

import os

os.environ["DB_BACKEND"] = "memory"
