from typing import List

from modelos import Object
from simpletransformers.classification import ClassificationModel, ClassificationArgs
import pandas as pd


class TextClassifier(Object):
    model: ClassificationModel

    def __init__(self, model_args: ClassificationArgs) -> None:
        self.model = ClassificationModel("bert", "bert-base-cased", num_labels=3, args=model_args)

    def train(self, df: pd.DataFrame) -> None:
        self.model.train_model(df)

    def predict(self, txt: str) -> List[int]:
        preds, _ = self.model.predict([txt])
        return preds


if __name__ == "__main__":
    TextClassifierClient = TextClassifier.client(hot=True)
    model_args = ClassificationArgs(num_train_epochs=1)

    with TextClassifierClient(model_args) as model:
        train_data = [
            ["Aragorn was the heir of Isildur", 1],
            ["Frodo was the heir of Isildur", 0],
        ]
        train_df = pd.DataFrame(train_data)
        train_df.columns = ["text", "labels"]

        model.train(train_df)
        uri = model.store("aunum/ml-project")

    model = TextClassifier.from_uri(uri)
    preds = model.predict("Merrry is stronger than Pippin")
