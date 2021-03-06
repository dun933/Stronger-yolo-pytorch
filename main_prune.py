from models.yolov3 import YoloV3
from trainers import *
import json
from yacscfg import _C as cfg
import os
from torch import optim
import argparse
import numpy as np
from thop import clever_format,profile
from pruning.l1norm import l1normPruner
from pruning.slimming import SlimmingPruner
from mmcv.runner import load_checkpoint
import torch

def main(args):
    gpus=[str(g) for g in args.devices]
    os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(gpus)
    model = YoloV3(numclass=args.MODEL.numcls,gt_per_grid=args.MODEL.gt_per_grid).cuda().eval()
    newmodel = YoloV3(numclass=args.MODEL.numcls,gt_per_grid=args.MODEL.gt_per_grid).cuda().eval()

    optimizer = optim.Adam(model.parameters(),lr=args.OPTIM.lr_initial)
    scheduler=optim.lr_scheduler.MultiStepLR(optimizer, milestones=args.OPTIM.milestones, gamma=0.1)
    _Trainer = eval('Trainer_{}'.format(args.DATASET.dataset))(args=args,
                       model=model,
                       optimizer=optimizer,
                       lrscheduler=scheduler
                       )

    pruner=SlimmingPruner(_Trainer,newmodel,pruneratio=args.Prune.pruneratio)
    # pruner=l1normPruner(_Trainer,newmodel,pruneratio=0.)
    pruner.prune()
    ##---------count op
    input=torch.randn(1,3,512,512).cuda()
    flops, params = profile(model, inputs=(input, ),verbose=False)
    flops, params = clever_format([flops, params], "%.3f")
    flopsnew, paramsnew = profile(newmodel, inputs=(input, ),verbose=False)
    flopsnew, paramsnew = clever_format([flopsnew, paramsnew], "%.3f")
    print("flops:{}->{}, params: {}->{}".format(flops,flopsnew,params,paramsnew))
    resultold=pruner.test(newmodel=False,validiter=10)
    resultnew=pruner.test(newmodel=True,validiter=10)
    print("original map:{},pruned map:{}".format(resultold,resultnew))
    bestfinetune=pruner.finetune()
    print("finetuned map:{}".format(bestfinetune))

    # load_checkpoint(newmodel, torch.load(os.path.join(_Trainer.save_path,'checkpoint-best-ft0.2.pth')))
    # pruner.test(newmodel=True,validiter=-1)
  #
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="DEMO configuration")
    parser.add_argument(
        "--config-file",
        default='configs/voc_prune.yaml'
    )

    parser.add_argument(
        "opts",
        help="Modify config options using the command-line",
        default=None,
        nargs=argparse.REMAINDER,
    )
    args = parser.parse_args()
    cfg.merge_from_file(args.config_file)
    cfg.merge_from_list(args.opts)
    cfg.freeze()
    main(args=cfg).run()
