class QaDatabaseRouter:
    alias = "rsjc_qa"
    app = "qa_monitor"

    def db_for_read(self, model, **hints):
        return self.alias if model._meta.app_label == self.app else None

    db_for_write = db_for_read

    def allow_relation(self, obj1, obj2, **hints):
        first = obj1._meta.app_label == self.app
        second = obj2._meta.app_label == self.app
        if first or second:
            return first and second
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == self.alias or app_label == self.app:
            return db == self.alias and app_label == self.app
        return None
