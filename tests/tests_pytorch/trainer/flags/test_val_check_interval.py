# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

import pytest
from torch.utils.data import DataLoader

from pytorch_lightning.demos.boring_classes import BoringModel, RandomDataset
from pytorch_lightning.trainer.trainer import Trainer
from pytorch_lightning.utilities.exceptions import MisconfigurationException
from tests_pytorch.helpers.datasets import RandomIterableDataset


@pytest.mark.parametrize("max_epochs", [1, 2, 3])
@pytest.mark.parametrize("denominator", [1, 3, 4])
def test_val_check_interval(tmpdir, max_epochs, denominator):
    class TestModel(BoringModel):
        def __init__(self):
            super().__init__()
            self.train_epoch_calls = 0
            self.val_epoch_calls = 0

        def on_train_epoch_start(self) -> None:
            self.train_epoch_calls += 1

        def on_validation_epoch_start(self) -> None:
            if not self.trainer.sanity_checking:
                self.val_epoch_calls += 1

    model = TestModel()
    trainer = Trainer(max_epochs=max_epochs, val_check_interval=1 / denominator, logger=False)
    trainer.fit(model)

    assert model.train_epoch_calls == max_epochs
    assert model.val_epoch_calls == max_epochs * denominator


@pytest.mark.parametrize("value", (1, 1.0))
def test_val_check_interval_info_message(caplog, value):
    with caplog.at_level(logging.INFO):
        Trainer(val_check_interval=value)
    assert f"`Trainer(val_check_interval={value})` was configured" in caplog.text
    message = "configured so validation will run"
    assert message in caplog.text

    caplog.clear()

    # the message should not appear by default
    with caplog.at_level(logging.INFO):
        Trainer()
    assert message not in caplog.text


@pytest.mark.parametrize("use_infinite_dataset", [True, False])
def test_validation_check_interval_exceed_data_length_correct(tmpdir, use_infinite_dataset):
    data_samples_train = 4
    max_epochs = 3
    max_steps = data_samples_train * max_epochs

    class TestModel(BoringModel):
        def __init__(self):
            super().__init__()
            self.validation_called_at_step = set()

        def validation_step(self, *args):
            self.validation_called_at_step.add(self.global_step)
            return super().validation_step(*args)

        def train_dataloader(self):
            train_ds = (
                RandomIterableDataset(32, count=max_steps + 100)
                if use_infinite_dataset
                else RandomDataset(32, length=data_samples_train)
            )
            return DataLoader(train_ds)

    model = TestModel()
    trainer = Trainer(
        default_root_dir=tmpdir,
        limit_val_batches=1,
        max_steps=max_steps,
        val_check_interval=3,
        check_val_every_n_epoch=None,
        num_sanity_val_steps=0,
    )

    trainer.fit(model)

    assert trainer.current_epoch == 1 if use_infinite_dataset else max_epochs
    assert trainer.global_step == max_steps
    assert sorted(list(model.validation_called_at_step)) == [3, 6, 9, 12]


def test_validation_check_interval_exceed_data_length_wrong():
    trainer = Trainer(
        limit_train_batches=10,
        val_check_interval=100,
    )

    model = BoringModel()
    with pytest.raises(ValueError, match="must be less than or equal to the number of the training batches"):
        trainer.fit(model)


def test_val_check_interval_float_with_none_check_val_every_n_epoch():
    """Test that an exception is raised when `val_check_interval` is set to float with
    `check_val_every_n_epoch=None`"""
    with pytest.raises(
        MisconfigurationException, match="`val_check_interval` should be an integer when `check_val_every_n_epoch=None`"
    ):
        Trainer(
            val_check_interval=0.5,
            check_val_every_n_epoch=None,
        )
