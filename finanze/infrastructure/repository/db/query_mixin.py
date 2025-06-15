class QueryMixin:
    def parse_block(self, block: str) -> list[str]:
        ddl_without_comments = "\n".join(
            [
                line
                for line in block.split("\n")
                if not line.strip().startswith("--") and line.strip() != ""
            ]
        )
        statements = [
            statement.strip()
            for statement in ddl_without_comments.split(";")
            if statement.strip()
        ]
        return statements
