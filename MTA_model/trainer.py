import time
import random

import torch
import torch.nn as nn
import torch.optim as optim

from utils import epoch_time
from model.optim import ScheduledAdam
from model.transformer import Transformer
from model.loss import MTA_Loss

random.seed(32)
torch.manual_seed(32)
torch.backends.cudnn.deterministic = True

class Trainer:
    def __init__(self, params, mode, train_iter=None, valid_iter=None, test_iter=None):
        self.params = params

        if mode == 'train':
            self.train_iter = train_iter
            self.valid_iter = valid_iter
        else:
            self.test_iter = test_iter

        self.model = Transformer(self.params)
        self.model.to(self.params.device)

        self.optimizer = ScheduledAdam(
            optim.Adam(self.model.parameters(), betas=(0.9, 0.98), eps=1e-9),
            hidden_dim=params.hidden_dim,
            warm_steps=params.warm_steps
        )

        self.criterion = MTA_Loss()
        self.criterion.to(self.params.device)

    def train(self):
        print(self.model)
        print(f'The model has {self.model.count_params():,} trainable parameters')
        best_valid_loss = float('inf')

        for epoch in range(self.params.num_epoch):
            self.model.train()
            epoch_loss = 0
            start_time = time.time()

            for batch in self.train_iter:
                self.optimizer.zero_grad()

                cam_sequential = torch.stack([item['cam_sequential'] for item in batch])
                cate_sequential = torch.stack([item['cate_sequential'] for item in batch])
                brand_sequential = torch.stack([item['price_sequential'] for item in batch])
                price_sequential = torch.stack([item['price_sequential'] for item in batch])
                segment = torch.stack([item['segment'] for item in batch])
                cms_label = torch.stack([item['cms'] for item in batch])
                gender_label = torch.stack([item['gender'] for item in batch])
                age_label = torch.stack([item['age'] for item in batch])
                pvalue_label = torch.stack([item['pvalue'] for item in batch])
                shopping_label = torch.stack([item['shopping'] for item in batch])
                conversion_label = torch.stack([item['label'] for item in batch])

                cms_output, gender_output, age_output, pvalue_output, shopping_output, conversion_output, attn_map = self.model(
                    cam_sequential, cate_sequential, price_sequential, segment)

                output = conversion_output.contiguous().view(-1, conversion_output.shape[-1]).squeeze(1)
                target = conversion_label.contiguous().view(-1)
                loss = self.criterion(cms_output, cms_label, gender_output, gender_label, age_output, age_label,
                                        pvalue_output, pvalue_label, shopping_output, shopping_label, output, target)

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.params.clip)
                self.optimizer.step()

                epoch_loss += loss.item()

            train_loss = epoch_loss / len(self.train_iter)
            valid_loss = self.evaluate()

            end_time = time.time()
            epoch_mins, epoch_secs = epoch_time(start_time, end_time)

            if valid_loss < best_valid_loss:
                best_valid_loss = valid_loss
                torch.save(self.model.state_dict(), self.params.save_model)

            print(f'Epoch: {epoch + 1:02} | Epoch Time: {epoch_mins}m {epoch_secs}s')
            print(f'\tTrain Loss: {train_loss:.3f} | Val. Loss: {valid_loss:.3f}')

    def evaluate(self):
        self.model.eval()
        epoch_loss = 0 # 에폭 로스 0으로 설정

        with torch.no_grad():
            for batch in self.valid_iter: 
                cam_sequential = batch.cam_sequential
                cate_sequential = batch.cate_sequential
                brand_sequential = batch.brand_sequential
                price_sequential = batch.price_sequential
                segment = batch.segment
                cms_label = batch.cms
                gender_label = batch.gender
                age_label = batch.age
                pvalue_label = batch.pvalue
                shopping_label = batch.shopping
                conversion_label = batch.label

                cms_output, gender_output, age_output, pvalue_output, shopping_output, conversion_output, attn_map = self.model(cam_sequential,cate_sequential,brand_sequential,price_sequential,segment)

                output = output.contiguous().view(-1, output.shape[-1])
                target = target[:, 1:].contiguous().view(-1)

                output = output.contiguous().view(-1, output.shape[-1]) 
                target = target[:, 1:].contiguous().view(-1) 
                loss = self.criterion(cms_output,cms_label,gender_output, gender_label, age_output, age_label,
                    pvalue_output, pvalue_label, shopping_output, shopping_label,conversion_output,conversion_label)

                epoch_loss += loss.item()

        return epoch_loss / len(self.valid_iter)

    def inference(self):
        self.model.load_state_dict(torch.load(self.params.save_model))
        self.model.eval()
        epoch_loss = 0

        with torch.no_grad():
            for batch in self.test_iter:
                cam_sequential = batch.cam_sequential
                cate_sequential = batch.cate_sequential
                brand_sequential = batch.brand_sequential
                price_sequential = batch.price_sequential
                segment = batch.segment
                cms_label = batch.cms
                gender_label = batch.gender
                age_label = batch.age
                pvalue_label = batch.pvalue
                shopping_label = batch.shopping
                conversion_label = batch.label

                cms_output, gender_output, age_output, pvalue_output, shopping_output, conversion_output, attn_map = self.model(cam_sequential,cate_sequential,brand_sequential,price_sequential,segment)

                output = output.contiguous().view(-1, output.shape[-1])
                target = target[:, 1:].contiguous().view(-1)

                loss = self.criterion(cms_output,cms_label,gender_output, gender_label, age_output, age_label,
                    pvalue_output, pvalue_label, shopping_output, shopping_label,conversion_output,conversion_label)

                epoch_loss += loss.item()

        test_loss = epoch_loss / len(self.test_iter)
        print(f'Test Loss: {test_loss:.3f}')
