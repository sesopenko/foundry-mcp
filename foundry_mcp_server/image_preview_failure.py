"""Lightweight fixed-category failures shared by parent and native worker modules."""


class PreviewFailure(Exception):
    def __init__(self, code, width=None, height=None):
        self.code,self.width,self.height = code,width,height
        super().__init__(code)
