from typing import Any, Callable, List, Optional

import pytorch_lightning as pl
import torch
import wandb
from audio_data_pytorch.utils import fractional_random_split
from audio_diffusion_pytorch import AudioDiffusionModel, Sampler, Schedule
from einops import rearrange
from pytorch_lightning import Callback, Trainer
from pytorch_lightning.loggers import LoggerCollection, WandbLogger
from torch.utils.data import DataLoader

""" Model """


class Model(pl.LightningModule):
    def __init__(
        self, learning_rate: float, beta1: float, beta2: float, *args, **kwargs
    ):
        super().__init__()
        self.learning_rate = learning_rate
        self.beta1 = beta1
        self.beta2 = beta2
        self.model = AudioDiffusionModel(*args, **kwargs)

    @property
    def device(self):
        return next(self.model.parameters()).device

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(
            list(self.parameters()),
            lr=self.learning_rate,
            betas=(self.beta1, self.beta2),
        )
        return optimizer

    def training_step(self, batch, batch_idx):
        waveforms = batch
        loss = self.model(waveforms)
        self.log("train_loss", loss)
        return loss

    def validation_step(self, batch, batch_idx):
        waveforms = batch
        loss = self.model(waveforms)
        self.log("valid_loss", loss)
        return loss


""" Datamodule """


class Datamodule(pl.LightningDataModule):
    def __init__(
        self,
        dataset,
        *,
        val_split: float,
        batch_size: int,
        num_workers: int,
        pin_memory: bool = False,
        **kwargs: int,
    ) -> None:
        super().__init__()
        self.dataset = dataset
        self.val_split = val_split
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.pin_memory = pin_memory
        self.data_train: Any = None
        self.data_val: Any = None

    def setup(self, stage: Any = None) -> None:
        split = [1.0 - self.val_split, self.val_split]
        self.data_train, self.data_val = fractional_random_split(self.dataset, split)

    def train_dataloader(self) -> DataLoader:
        return DataLoader(
            dataset=self.data_train,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            shuffle=True,
        )

    def val_dataloader(self) -> DataLoader:
        return DataLoader(
            dataset=self.data_val,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            pin_memory=self.pin_memory,
            shuffle=True,
        )


""" Callbacks """


def get_wandb_logger(trainer: Trainer) -> Optional[WandbLogger]:
    """Safely get Weights&Biases logger from Trainer."""

    if isinstance(trainer.logger, WandbLogger):
        return trainer.logger

    if isinstance(trainer.logger, LoggerCollection):
        for logger in trainer.logger:
            if isinstance(logger, WandbLogger):
                return logger

    print("WandbLogger not found.")
    return None


class SampleLogger(Callback):
    def __init__(
        self,
        num_items: int,
        channels: int,
        sampling_rate: int,
        length: int,
        sampling_steps: List[int],
        diffusion_schedule: Schedule,
        diffusion_sampler: Sampler,
    ) -> None:
        self.num_items = num_items
        self.channels = channels
        self.sampling_rate = sampling_rate
        self.length = length
        self.sampling_steps = sampling_steps
        self.diffusion_schedule = diffusion_schedule
        self.diffusion_sampler = diffusion_sampler

        self.log_next = False

    def on_validation_epoch_start(self, trainer, pl_module):
        self.log_next = True

    def on_validation_batch_start(
        self, trainer, pl_module, batch, batch_idx, dataloader_idx
    ):
        if self.log_next:
            self.log_sample(trainer, pl_module, batch)
            self.log_next = False

    @torch.no_grad()
    def log_sample(self, trainer, pl_module, batch):
        is_train = pl_module.training
        if is_train:
            pl_module.eval()

        wandb_logger = get_wandb_logger(trainer).experiment
        model = pl_module.model

        # Get start diffusion noise
        noise = torch.randn(
            (self.num_items, self.channels, self.length), device=pl_module.device
        )

        for steps in self.sampling_steps:

            samples = model.sample(
                noise=noise,
                sampler=self.diffusion_sampler,
                sigma_schedule=self.diffusion_schedule,
                num_steps=steps,
            )
            samples = rearrange(samples, "b c t -> b t c").detach().cpu().numpy()

            wandb_logger.log(
                {
                    f"sample_{idx}_{steps}": wandb.Audio(
                        samples[idx],
                        caption=f"Sampled in {steps} steps",
                        sample_rate=self.sampling_rate,
                    )
                    for idx in range(self.num_items)
                }
            )

        if is_train:
            pl_module.train()
