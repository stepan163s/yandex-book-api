import ast
from pathlib import Path

ROOT = Path(__file__).parent
CLIENT_SRC = ROOT / 'yandex_book' / 'client.py'
CLIENT_DST = ROOT / 'yandex_book' / 'client_async.py'
REQUEST_ASYNC_METHODS = {'get', 'post', 'delete', 'graphql', 'retrieve', 'download', 'close'}
REQUEST_SYNC_METHODS = {'set_token', 'set_language'}
DUNDER_NAMES = {'__enter__': '__aenter__', '__exit__': '__aexit__'}


class AsyncClientTransformer(ast.NodeTransformer):
    def __init__(self, methods):
        self.methods = methods
        self.in_client = False
        self.in_async = False

    def visit_ImportFrom(self, node):
        if node.module == 'yandex_book.utils.request':
            node.module = 'yandex_book.utils.request_async'
            node.names = [ast.alias(name='RequestAsync', asname='Request')]
        return node

    def visit_ClassDef(self, node):
        previous = self.in_client
        self.in_client = node.name == 'YandexBookClient'
        if self.in_client:
            node.name = 'YandexBookClientAsync'
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body[0].value.value = node.body[0].value.value.replace(
                    'Синхронный клиент', 'Асинхронный клиент')
        node = self.generic_visit(node)
        self.in_client = previous
        return node

    def visit_FunctionDef(self, node):
        make_async = (self.in_client and node.name in self.methods) or node.name == 'wrapper'
        previous = self.in_async
        self.in_async = make_async
        node = self.generic_visit(node)
        self.in_async = previous
        if make_async:
            node.name = DUNDER_NAMES.get(node.name, node.name)
            node = ast.AsyncFunctionDef(**{field: getattr(node, field) for field in node._fields})
        return node

    def visit_AnnAssign(self, node):
        if self.in_client and isinstance(node.target, ast.Name) and node.target.id == '_is_async':
            node.value = ast.Constant(True)
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if node.value == 'YandexBookClient':
            node.value = 'YandexBookClientAsync'
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if not self.in_async:
            return node
        func = node.func
        awaited = isinstance(func, ast.Name) and func.id == 'method'
        if isinstance(func, ast.Attribute):
            owner = func.value
            if isinstance(owner, ast.Name) and owner.id == 'self':
                awaited = func.attr in self.methods
            elif (isinstance(owner, ast.Attribute) and owner.attr == '_request'
                  and isinstance(owner.value, ast.Name) and owner.value.id == 'self'):
                if func.attr not in REQUEST_ASYNC_METHODS | REQUEST_SYNC_METHODS:
                    raise ValueError(f'Неизвестный метод HTTP-слоя: {func.attr}')
                awaited = func.attr in REQUEST_ASYNC_METHODS
        return ast.Await(value=node) if awaited else node


def render_async(source: str) -> str:
    tree = ast.parse(source)
    if ast.get_docstring(tree):
        tree.body[0].value.value = (
            'Асинхронный клиент Яндекс Книг / Bookmate API.\n\n'
            'Сгенерирован из client.py командой python generate_async_version.py.\n'
            'Изменения вносите в исходный синхронный клиент.'
        )
    client = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                  and node.name == 'YandexBookClient')
    methods = {node.name for node in client.body if isinstance(node, ast.FunctionDef)
               and (not node.name.startswith('__') or node.name in DUNDER_NAMES)}
    tree = AsyncClientTransformer(methods).visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + '\n'


def generate_client_async() -> None:
    CLIENT_DST.write_text(render_async(CLIENT_SRC.read_text(encoding='utf-8')), encoding='utf-8')
    print(f'Создан: {CLIENT_DST}')


if __name__ == '__main__':
    generate_client_async()
