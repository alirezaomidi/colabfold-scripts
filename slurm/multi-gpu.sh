#!/bin/bash
#SBATCH --job-name=colabfold
#SBATCH --account=def-gsponer  # or rrg-gsponer
#SBATCH --time=2-23:58:00
#SBATCH --nodes=1
#SBATCH --array=0-0
#SBATCH --gpus-per-node=v100l:4  # you can adjust this based on the cluster. see: https://docs.alliancecan.ca/wiki/Using_GPUs_with_Slurm#Whole_nodes
#SBATCH --cpus-per-task=32  # refer to the same link above
#SBATCH --mem=0
#SBATCH --output=outputs/%A.%a.out

module load StdEnv/2020 gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2

source ~/alphafold_env/bin/activate

# print gpu info
nvidia-smi

BEGIN=$(($SLURM_ARRAY_TASK_ID * 4))
END=$(($BEGIN + 3))

echo "$@"
srun parallel -j4 CUDA_VISIBLE_DEVICES='{=1 $_=$arg[1]%4 =}' python -u batch.py \
     --n-batch 4 \
     --batch-id {} \
     $@ ::: $(seq $BEGIN $END)
