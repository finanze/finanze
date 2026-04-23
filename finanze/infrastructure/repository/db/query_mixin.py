class QueryMixin:
    def parse_block(self, block: str) -> list[str]:
        ddl_without_comments = "\n".join(
            [
                line
                for line in block.split("\n")
                if not line.strip().startswith("--") and line.strip() != ""
            ]
        )
        statements: list[str] = []
        for raw in ddl_without_comments.split(";"):
            stmt = raw.strip()
            if not stmt:
                continue
            if stmt.startswith("--"):
                continue
            statements.append(stmt)
        return statements
