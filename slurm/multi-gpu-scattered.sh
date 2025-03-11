#!/bin/bash
#SBATCH --job-name=colabfold
#SBATCH --account=def-gsponer  # or rrg-gsponer
#SBATCH --time=11:58:00
#SBATCH --array=0-1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=60G
#SBATCH --output=outputs/%A.%a.out

module load StdEnv/2020 gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2

source ~/alphafold_env/bin/activate

# print gpu info
nvidia-smi

echo "$@"
srun python -u batch.py \
     --n-batch 2 \
     --batch-id $SLURM_ARRAY_TASK_ID \
     $@
