from argparse import ArgumentParser
from pathlib import Path
import os
import sys
import warnings
import contextlib
import requests
import importlib_metadata
from colabfold.batch import run, ENV, set_model_type, get_queries, get_msa_and_templates, unserialize_msa, msa_to_str, mk_hhsearch_db
from colabfold.download import default_data_dir, download_alphafold_params
from colabfold.utils import DEFAULT_API_SERVER, get_commit, setup_logging, ACCEPT_DEFAULT_TERMS, safe_filename
from urllib3.exceptions import InsecureRequestWarning
import logging

# logging settings
logger = logging.getLogger(__name__)

# disable ssl verification
old_merge_environment_settings = requests.Session.merge_environment_settings

@contextlib.contextmanager
def no_ssl_verification():
    opened_adapters = set()

    def merge_environment_settings(self, url, proxies, stream, verify, cert):
        # Verification happens only once per connection so we need to close
        # all the opened adapters once we're done. Otherwise, the effects of
        # verify=False persist beyond the end of this context manager.
        opened_adapters.add(self.get_adapter(url))

        settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
        settings['verify'] = False

        return settings

    requests.Session.merge_environment_settings = merge_environment_settings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            yield
    finally:
        requests.Session.merge_environment_settings = old_merge_environment_settings

        for adapter in opened_adapters:
            try:
                adapter.close()
            except:
                pass


def get_msas(
        queries,
        result_dir,
        msa_mode,
        use_templates,
        custom_template_path,
        keep_existing_results,
        pair_mode,
        pairing_strategy,
        host_url,
        user_agent
    ):
    result_dir = Path(result_dir)
    result_dir.mkdir(exist_ok=True)

    if custom_template_path is not None:
        mk_hhsearch_db(custom_template_path)

    for job_number, (raw_jobname, query_sequence, a3m_lines) in enumerate(queries):
        jobname = safe_filename(raw_jobname)

        #######################################
        # check if job has already finished
        #######################################
        # In the colab version and with --zip we know we're done when a zip file has been written
        result_zip = result_dir.joinpath(jobname).with_suffix(".result.zip")
        if keep_existing_results and result_zip.is_file():
            logger.info(f"Skipping {jobname} (result.zip)")
            continue
        # In the local version we use a marker file
        is_done_marker = result_dir.joinpath(jobname + ".done.txt")
        if keep_existing_results and is_done_marker.is_file():
            logger.info(f"Skipping {jobname} (already done)")
            continue

        seq_len = len("".join(query_sequence))
        logger.info(f"Query {job_number + 1}/{len(queries)}: {jobname} (length {seq_len})")

        ###########################################
        # generate MSA (a3m_lines) and templates
        ###########################################
        try:
            if a3m_lines is None:
                (unpaired_msa, paired_msa, query_seqs_unique, query_seqs_cardinality, template_features) \
                = get_msa_and_templates(jobname, query_sequence, a3m_lines, result_dir, msa_mode, use_templates,
                    custom_template_path, pair_mode, pairing_strategy, host_url, user_agent)

            elif a3m_lines is not None:
                (unpaired_msa, paired_msa, query_seqs_unique, query_seqs_cardinality, template_features) \
                = unserialize_msa(a3m_lines, query_sequence)
                if use_templates:
                    (_, _, _, _, template_features) \
                        = get_msa_and_templates(jobname, query_seqs_unique, unpaired_msa, result_dir, 'single_sequence', use_templates,
                            custom_template_path, pair_mode, pairing_strategy, host_url, user_agent)

            # save a3m
            msa = msa_to_str(unpaired_msa, paired_msa, query_seqs_unique, query_seqs_cardinality)
            result_dir.joinpath(f"{jobname}.a3m").write_text(msa)

        except Exception as e:
            logger.exception(f"Could not get MSA/templates for {jobname}: {e}")
            continue


def main():
    parser = ArgumentParser()
    parser.add_argument("input",
        default="input",
        help="Can be one of the following: "
        "Directory with fasta/a3m files, a csv/tsv file, a fasta file or an a3m file",
    )
    parser.add_argument("results", help="Directory to write the results to")
    parser.add_argument("--stop-at-score",
        help="Compute models until plddt (single chain) or ptmscore (complex) > threshold is reached. "
        "This can make colabfold much faster by only running the first model for easy queries.",
        type=float,
        default=100,
    )
    parser.add_argument("--num-recycle",
        help="Number of prediction recycles."
        "Increasing recycles can improve the quality but slows down the prediction.",
        type=int,
        default=None,
    )
    parser.add_argument("--recycle-early-stop-tolerance",
        help="Specify convergence criteria."
        "Run until the distance between recycles is within specified value.",
        type=float,
        default=None,
    )
    parser.add_argument("--num-ensemble",
        help="Number of ensembles."
        "The trunk of the network is run multiple times with different random choices for the MSA cluster centers.",
        type=int,
        default=1,
    )
    parser.add_argument("--num-seeds",
        help="Number of seeds to try. Will iterate from range(random_seed, random_seed+num_seeds)."
        ".",
        type=int,
        default=1,
    )
    parser.add_argument("--random-seed",
        help="Changing the seed for the random number generator can result in different structure predictions.",
        type=int,
        default=0,
    )
    parser.add_argument("--num-models", type=int, default=5, choices=[1, 2, 3, 4, 5])
    parser.add_argument("--recompile-padding",
        type=int,
        default=10,
        help="Whenever the input length changes, the model needs to be recompiled."
        "We pad sequences by specified length, so we can e.g. compute sequence from length 100 to 110 without recompiling."
        "The prediction will become marginally slower for the longer input, "
        "but overall performance increases due to not recompiling. "
        "Set to 0 to disable.",
    )
    parser.add_argument("--model-order", default="1,2,3,4,5", type=str)
    parser.add_argument("--host-url", default=DEFAULT_API_SERVER)
    parser.add_argument("--data")
    parser.add_argument("--msa-mode",
        default="mmseqs2_uniref_env",
        choices=[
            "mmseqs2_uniref_env",
            "mmseqs2_uniref",
            "single_sequence",
        ],
        help="Using an a3m file as input overwrites this option",
    )
    parser.add_argument("--model-type",
        help="predict strucutre/complex using the following model."
        'Auto will pick "alphafold2_ptm" for structure predictions and "alphafold2_multimer_v3" for complexes.',
        type=str,
        default="auto",
        choices=[
            "auto",
            "alphafold2",
            "alphafold2_ptm",
            "alphafold2_multimer_v1",
            "alphafold2_multimer_v2",
            "alphafold2_multimer_v3",
        ],
    )
    parser.add_argument("--amber",
        default=False,
        action="store_true",
        help="Use amber for structure refinement."
        "To control number of top ranked structures are relaxed set --num-relax.",
    )
    parser.add_argument("--num-relax",
        help="specify how many of the top ranked structures to relax using amber.",
        type=int,
        default=0,
    )
    parser.add_argument("--templates", default=False, action="store_true", help="Use templates from pdb")
    parser.add_argument("--custom-template-path",
        type=str,
        default=None,
        help="Directory with pdb files to be used as input",
    )
    parser.add_argument("--rank",
        help="rank models by auto, plddt or ptmscore",
        type=str,
        default="auto",
        choices=["auto", "plddt", "ptm", "iptm", "multimer"],
    )
    parser.add_argument("--pair-mode",
        help="rank models by auto, unpaired, paired, unpaired_paired",
        type=str,
        default="unpaired_paired",
        choices=["unpaired", "paired", "unpaired_paired"],
    )
    parser.add_argument("--sort-queries-by",
        help="sort queries by: none, length, random",
        type=str,
        default="length",
        choices=["none", "length", "random"],
    )
    parser.add_argument("--save-single-representations",
        default=False,
        action="store_true",
        help="saves the single representation embeddings of all models",
    )
    parser.add_argument("--save-pair-representations",
        default=False,
        action="store_true",
        help="saves the pair representation embeddings of all models",
    )
    parser.add_argument("--use-dropout",
        default=False,
        action="store_true",
        help="activate dropouts during inference to sample from uncertainity of the models",
    )
    parser.add_argument("--max-seq",
        help="number of sequence clusters to use",
        type=int,
        default=None,
    )
    parser.add_argument("--max-extra-seq",
        help="number of extra sequences to use",
        type=int,
        default=None,
    )
    parser.add_argument("--max-msa",
        help="defines: `max-seq:max-extra-seq` number of sequences to use",
        type=str,
        default=None,
    )
    parser.add_argument("--disable-cluster-profile",
        default=False,
        action="store_true",
        help="EXPERIMENTAL: for multimer models, disable cluster profiles",
    )
    parser.add_argument("--zip",
        default=False,
        action="store_true",
        help="zip all results into one <jobname>.result.zip and delete the original files",
    )
    parser.add_argument("--use-gpu-relax",
        default=False,
        action="store_true",
        help="run amber on GPU instead of CPU",
    )
    parser.add_argument("--save-all",
        default=False,
        action="store_true",
        help="save ALL raw outputs from model to a pickle file",
    )
    parser.add_argument("--save-recycles",
        default=False,
        action="store_true",
        help="save all intermediate predictions at each recycle",
    )
    parser.add_argument("--overwrite-existing-results", default=False, action="store_true")
    parser.add_argument("--disable-unified-memory",
        default=False,
        action="store_true",
        help="if you are getting tensorflow/jax errors it might help to disable this",
    )
    parser.add_argument('--n-batch', type=int, default=1, help='Number of batches to split the input into')
    parser.add_argument('--batch-id', type=int, default=0, help='Batch id to run on')
    parser.add_argument('--only-msa', default=False, action="store_true", help='Only run MSA')

    args = parser.parse_args()

    # disable unified memory
    if args.disable_unified_memory:
        for k in ENV.keys():
            if k in os.environ: del os.environ[k]

    setup_logging(Path(args.results).joinpath("log.txt"))

    version = importlib_metadata.version("colabfold")
    commit = get_commit()
    if commit:
        version += f" ({commit})"
    user_agent = f"colabfold/{version}"

    logger.info(f"Running colabfold {version}")

    data_dir = Path(args.data or default_data_dir)

    queries, is_complex = get_queries(args.input, args.sort_queries_by)
    # choose the batch
    queries = queries[args.batch_id::args.n_batch]

    if args.msa_mode != "single_sequence" and not args.templates:
        uses_api = any((query[2] is None for query in queries))
        if uses_api and args.host_url == DEFAULT_API_SERVER:
            print(ACCEPT_DEFAULT_TERMS, file=sys.stderr)

    if args.only_msa:
        with no_ssl_verification():
            get_msas(
                queries=queries,
                result_dir=args.results,
                msa_mode=args.msa_mode,
                use_templates=args.templates,
                custom_template_path=args.custom_template_path,
                keep_existing_results=not args.overwrite_existing_results,
                pair_mode=args.pair_mode,
                pairing_strategy=args.pair_mode,
                host_url=args.host_url,
                user_agent=user_agent,
            )
        return

    model_type = set_model_type(is_complex, args.model_type)

    with no_ssl_verification():
        download_alphafold_params(model_type, data_dir)

    model_order = [int(i) for i in args.model_order.split(",")]

    assert args.recompile_padding >= 0, "Can't apply negative padding"

    # backward compatibility
    if args.amber and args.num_relax == 0:
        args.num_relax = args.num_models * args.num_seeds

    with no_ssl_verification():
        run(
            queries=queries,
            result_dir=args.results,
            use_templates=args.templates,
            custom_template_path=args.custom_template_path,
            num_relax=args.num_relax,
            msa_mode=args.msa_mode,
            model_type=model_type,
            num_models=args.num_models,
            num_recycles=args.num_recycle,
            recycle_early_stop_tolerance=args.recycle_early_stop_tolerance,
            num_ensemble=args.num_ensemble,
            model_order=model_order,
            is_complex=is_complex,
            keep_existing_results=not args.overwrite_existing_results,
            rank_by=args.rank,
            pair_mode=args.pair_mode,
            data_dir=data_dir,
            host_url=args.host_url,
            user_agent=user_agent,
            random_seed=args.random_seed,
            num_seeds=args.num_seeds,
            stop_at_score=args.stop_at_score,
            recompile_padding=args.recompile_padding,
            zip_results=args.zip,
            save_single_representations=args.save_single_representations,
            save_pair_representations=args.save_pair_representations,
            use_dropout=args.use_dropout,
            max_seq=args.max_seq,
            max_extra_seq=args.max_extra_seq,
            max_msa=args.max_msa,
            use_cluster_profile=not args.disable_cluster_profile,
            use_gpu_relax = args.use_gpu_relax,
            save_all=args.save_all,
            save_recycles=args.save_recycles,
        )


if __name__ == "__main__":
    main()