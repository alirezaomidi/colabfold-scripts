#!/bin/bash
sbatch <<EOT
#!/bin/bash
#SBATCH --job-name=colabfold
#SBATCH --account=def-gsponer
#SBATCH --time=2-23:58:00
#SBATCH --nodes=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=60G
#SBATCH --output=outputs/%A.%a.out
#SBATCH --mail-user=CWL@student.ubc.ca # adjust this to match your email address
#SBATCH --mail-type=END
#SBATCH --mail-type=FAIL

module load StdEnv/2020 gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2

source ~/alphafold_env/bin/activate

# print gpu info
nvidia-smi

# make the output directory
mkdir -p $2/

echo "$@"
srun python -u batch.py \
     --num-recycle 3 \
     --model-type alphafold2_multimer_v2 \
     --num-seeds 1 \
     --zip \
     --n-batch 1 \
     --batch-id 0 \
     $@

EOT
