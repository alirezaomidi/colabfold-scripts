# ColabFold Scripts
a few scripts to run ColabFold painlessly

## Install on Compute Canada
```bash
# load necessary modules
module load StdEnv/2020 gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2
# create a python virtual environment
virtualenv --no-download ~/alphafold_env
source ~/alphafold_env/bin/activate
# install colabfold and alphafold
pip install --no-index --upgrade pip
pip install --no-index alphafold
pip install --no-deps alphafold-colabfold
pip install --no-deps "colabfold[alphafold]@git+https://github.com/sokrypton/ColabFold" appdirs py3Dmol tqdm urllib3 requests
# test wheter we succeeded or not
python -m colabfold.batch
```

Then clone this repository:
```bash
cd ~/scratch/  # or any other base directory you want
git clone https://github.com/alirezaomidi/colabfold-scripts.git
cd colabfold-scripts/
```

## Run on Compute Canada
Since there is no access to the Internet on Graham and Narval compute nodes, you need to download AlphaFold model parameters and multiple sequence alignments on login nodes. Ignore these two steps on Cedar except you have 20 or more entries in your fasta file. In that case, do the MSA download part on Cedar login nodes to prevent rate limits.

Run the following script to download AlphaFold model parameters. This needs to be run only once. You can specify any:
```bash
cd ~/scratch/colabfold-scripts/
module load StdEnv/2020 gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2
source ~/alphafold_env/bin/activate

python batch.py path/to/dummy/fastafile.fasta /path/to/dummy/directory --model-type alphafold2_multimer_v2 --only-download-params
```

Refer to [MSA download section](#msa-public-server-rate-limit) for guidance on how to download multiple sequence alignments. This download should be done on login nodes.

Then, to use one GPU:
```bash
./slurm/single-gpu.sh path/to/fastafile.fasta ~/scratch/colabfold/exp/EXPERIMENTNAME
```
or to use multiple GPUs:
```bash
./slurm/multi-gpu.sh path/to/fastafile.fasta ~/scratch/colabfold/exp/EXPERIMENTNAME
```

Substitute `EXPERIMENTNAME` with an arbitrary experiment name. This is the directory where ColabFold will save all output files in.



If you want to use another AlphaFold version, change `alphafol2_multimer_v2`. A list of options can be found in `batch.py` file, under `model_type` argument.


## Array Jobs
The multi GPU run scripts use SLURM array jobs to simultaneously submit a few colabfold jobs. For example the following line will submit 8 parallel jobs:
```
#SBATCH --array=0-7
```
Since in each job we ask for full node allocations and make use of 4 GPUs in each node, we'll have 32 instances of ColabFold running in parallel. You can modify this number based on your needs. Suppose we want 8 instances of ColabFold in parallel. Then we need to modify 2 lines in the submission script:

1. Modify `#SBATCH --array=0-7` to `#SBATCH --array=0-1` to ask for 2 nodes
2. Modify `--n-batch 32` to `--n-batch 8` at the near bottom of the script.


## MSA Public Server Rate Limit
ColabFold's public MSA server [https://api.colabfold.com](https://api.colabfold.com) has a rate limit of a few request per minute. To avoid this rate limit, we can ask for MSAs before running the neural-network. To do so, Run the following **in a login node**:
```bash
cd ~/scratch/colabfold-scripts/
module load StdEnv/2020 gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2
source ~/alphafold_env/bin/activate

python batch.py path/to/fastafile.fasta ~/scratch/colabfold/exp/EXPERIMENTNAME --only-msa
```
This comamnd will request for MSAs one-by-one and save them in the `~/scratch/colabfold/exp/EXPERIMENTNAME/` directory. You can then submit the jobs as previously described. The jobs will automatically find the MSAs and use them instead of requesting new ones.

## Permission denied when running scripts
If you get a `Permission denied` error when running the scripts, run the following command:
```bash
chmod +x ~/scratch/colabfold-scripts/slurm/*.sh
```
