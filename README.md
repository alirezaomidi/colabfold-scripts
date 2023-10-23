# ColabFold Scripts
a few scripts to run ColabFold painlessly

## Compute Canada
### Install
```bash
# load necessary modules
module load gcc/9.3.0 openmpi/4.0.3 cuda/11.4 cudnn/8.2.0 kalign/2.03 hmmer/3.2.1 openmm-alphafold/7.5.1 hh-suite/3.3.0 python/3.8 mmseqs2
# create a python virtual environment
virtualenv --no-download ~/alphafold_env
source ~/alphafold_env/bin/activate
# install colabfold and alphafold
pip install --no-index --upgrade pip
pip install --no-index alphafold
pip install --no-deps alphafold-colabfold
pip install --no-deps "colabfold[alphafold]@git+https://github.com/sokrypton/ColabFold" appdirs py3Dmol tqdm
# test wheter we succeeded or not
python -m colabfold.batch
```

Then clone this repository:
```bash
cd ~/scratch/  # or any other base directory you want
git clone https://github.com/alirezaomidi/colabfold-scripts.git
cd colabfold-scripts/
```

### Run on Cedar
```bash
./slurm/cedar.sh path/to/fastafile.fasta ~/scratch/colabfold/exp/EXPERIMENTNAME
```
Substitute `EXPERIMENTNAME` with an arbitrary experiment name. This is the directory where ColabFold will save all output files in.

### Run on Graham:
To run on Graham, first install [sshpass](https://sourceforge.net/projects/sshpass/):
```bash
cd ~/
wget -O sshpass-1.10.tar.gz https://sourceforge.net/projects/sshpass/files/sshpass/1.10/sshpass-1.10.tar.gz/download
tar xvzf sshpass-1.10.tar.gz
cd sshpass-1.10
mkdir ./build
./configure --prefix=$PWD/build
make install
```

Then go back to the `~/scratch/colabfold-scripts` directory and use:
```bash
./slurm/graham.sh YOURPASSWORD path/to/fastafile.fasta ~/scratch/colabfold/exp/EXPERIMENTNAME
```
Substitute:
- `YOURPASSWORD` with your Compute Canada account's password
- `EXPERIMENTNAME` with an arbitrary experiment name. This is the directory where ColabFold will save all output files in.

### More on Run Scripts
The run scripts use SLURM array jobs to simultaneously submit a few colabfold jobs. 