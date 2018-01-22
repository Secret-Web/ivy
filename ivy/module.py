class Module:
    def __init__(self, ivy, config={}, logger=None):
        self.ivy = ivy

        self.config = config
        self.logger = logger

    def on_load(self):
        pass
