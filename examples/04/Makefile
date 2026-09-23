# 04 — 总表 4 CRLF job.sh（已完成）
# all 用 Python 写出 \r\n；仓库内 job.sh 同样为 CRLF。
.PHONY: all clean

all: job.sh

job.sh:
	python3 -c "from pathlib import Path; Path('job.sh').write_bytes(b'#!/bin/bash\r\necho crlf-fixture\r\nexit 1\r\n')"

clean:
	@true
