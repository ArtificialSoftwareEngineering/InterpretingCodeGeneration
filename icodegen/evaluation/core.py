# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_evaluation.core.ipynb (unless otherwise specified).

__all__ = ['get_mean_probs', 'find_parens', 'mean_dist_probs', 'get_mean_cross_entropy', 'evaluate']

# Cell
import numpy as np
import pandas as pd
import tensorflow as tf

from collections import Counter, defaultdict
from ..data.transforms import (
    code_token_randomizer,
    line_randomizer,
    java_comment_remover,
    transform_df,
)
from ..model.core import Model, RNNModel
from scipy import stats
from typing import Dict, List, Optional

# Cell
def get_mean_probs(df: pd.DataFrame, model: Model, n: Optional[int] = None):
    """
    Get the mean probability of each token that the model
    should predict for an entire pandas dataframe.

    :param df: the pandas dataframe containing each method to have the model predict on
    :param model: the model used to generate the predictions
    :param n: the number of methods to evaluate. If none, the entire dataframe will be used
    :returns: returns a numpy array of the mean probability for each token in the model's vocab
    """
    if n is None:
        n = len(df)

    # setup container lists for the number of occurrences and sum of probabilities for each token
    counts = [0] * model.tokenizer.get_vocab_size()
    sum_probs = [0.0] * model.tokenizer.get_vocab_size()
    # loop through each method
    for mthd in df.code.values[:n]:
        # token the method and generate the probabilities for the model's predictions
        inputs = model.tokenize(mthd)
        probs = model.get_probs(inputs)[0].numpy()

        # loop through each token and its probability and update the container lists
        for idx, p in zip(inputs["input_ids"][0], probs):
            counts[idx] += 1
            sum_probs[idx] += p[idx]

    # convert the lists to numpy lists and perform element wise division to get the mean probabilities for each token
    counts = np.array(counts)
    sum_probs = np.array(sum_probs)

    # perform division, but not when denominator is zero. In those cases, just leave value as NAN.
    nans = np.empty(counts.shape)
    nans.fill(np.nan)
    mean_probs = np.divide(sum_probs, counts, out=nans, where=counts != 0)
    # TODO: convert to dictionary with keys as tokens
    mean_probs = {
        model.tokenizer.id_to_token(i): mean_probs[i] for i in range(len(mean_probs))
    }
    return mean_probs

# Cell
def find_parens(toks: List[str], opening: str, closing: str) -> Dict[int, int]:
    """
    Get the indices for the opening and closing tokens.
    From https://stackoverflow.com/a/29992065/5768407
    by user Baltasarq (https://stackoverflow.com/users/266978/baltasarq).

    :param toks: the tokenized version of a method
    :param opening: the opening token that will be matched against the closing token
    :param closing: the closing token that will be matched against the opening token
    :returns: returns a dictionary with the opening token indices as the keys and the closing token indices as the values
    """
    toret = {}
    pstack = []

    for i, tok in enumerate(toks):
        if tok == opening:
            pstack.append(i)
        elif tok == closing:
            if len(pstack) == 0:
                raise IndexError("No matching closing parens at: " + str(i))
            toret[pstack.pop()] = i

    if len(pstack) > 0:
        raise IndexError("No matching opening parens at: " + str(pstack.pop()))

    return toret


def _get_dist_probs(
    mthd: str, model: Model, opening: str, closing: str
) -> Dict[int, float]:
    """
    Get the distances and mean probabilities between opening and closing tokens in a given method.

    :param mthd: the method to get the ranges of the opening and closing tokens and their probabilities
    :param model: the model used to generate the predictions
    :param opening: the opening token used for calculating the distance between opening and closing tokens
    :param closing: the closing token used for calculating the distance between opening and closing tokens as well as the token to get the mean probability of
    :returns: returns a dictionary with the distance between the opening and closing tokens as keys and their mean probabilities as values
    """
    # WARNING: Careful when using different tokenizers since HF tokenizers lib have diff API then HF transformers lib tokenizers... You will need to update this when using custom model and tokenizer...

    # get the distances for the opening and closing tokens
    toks = model.tokenizer.encode(mthd).tokens
    idxs = find_parens(toks, opening, closing)

    # get the model probabilities for the given method
    inputs = model.tokenize(mthd)
    probs = model.get_probs(inputs)[0].numpy()

    # sum up the probabilities of the different distances for the closing token
    dist_probs = defaultdict(float)
    for open_id, close_id in idxs.items():
        dist_probs[close_id - open_id] += probs[close_id][
            inputs["input_ids"][0][close_id]
        ]

    # get the mean of the summed probabilities
    dist_cnts = Counter([close_id - open_id for open_id, close_id in idxs.items()])
    dist_probs = {dist: dist_probs[dist] / n for dist, n in dist_cnts.items()}
    return dist_probs


def mean_dist_probs(
    df: pd.DataFrame,
    model: Model,
    opening: Optional[str] = "<{>",
    closing: Optional[str] = "<}>",
    n: Optional[int] = None,
) -> pd.DataFrame:
    """
    Get the distance between opening and closing tokens and the mean probability of each closing token that the model should predict for an entire pandas dataframe.

    :param df: the pandas dataframe containing each method to have the model predict on
    :param model: the model used to generate the predictions
    :param opening: the opening token used for calculating the distance between opening and closing tokens
    :param closing: the closing token used for calculating the distance between opening and closing tokens as well as the token to get the mean probability of
    :param n: the number of methods to evaluate. If none, the entire dataframe will be used
    :returns: returns a dataframe with the distances between opening and closing tokens and their mean probabilities
    """
    if n is None:
        n = len(df)

    # get the probabilities for the different distances for an entire dataframe
    df = df.iloc[:n].copy()
    dist_probs = df.code.apply(
        lambda mthd: _get_dist_probs(mthd, model, opening, closing)
    ).values

    # flatten the keys of the different distances into a list
    dist_keys = []
    for probs in dist_probs:
        dist_keys.extend(probs.keys())
    # merge dictionaries across methods by taking the mean of probs with the same distance. Modified from https://stackoverflow.com/a/10461916/5768407,
    # users georg https://stackoverflow.com/users/989121/georg and Rémy Hosseinkhan Boucher https://stackoverflow.com/users/12149730/r%c3%a9my-hosseinkhan-boucher
    mean_dist_probs = {
        k: np.nanmean(np.array([probs.get(k, np.nan) for probs in dist_probs]))
        for k in set(dist_keys)
    }
    std_dist_probs = {
        k: np.nanstd(np.array([probs.get(k, np.nan) for probs in dist_probs]))
        for k in set(dist_keys)
    }

    med_dist_probs = {
        k: np.nanmedian(np.array([probs.get(k, np.nan) for probs in dist_probs]))
        for k in set(dist_keys)
    }
    mad_dist_probs = {
        k: stats.median_abs_deviation(
            np.array([probs.get(k, np.nan) for probs in dist_probs]), nan_policy="omit"
        )
        for k in set(dist_keys)
    }
    # TODO: convert to dictionary
    df_dist = (
        pd.DataFrame(
            {
                "dist": list(mean_dist_probs.keys()),
                "mean_prob": list(mean_dist_probs.values()),
                "std_prob": list(std_dist_probs.values()),
                "med_prob": list(med_dist_probs.values()),
                "mad_prob": list(mad_dist_probs.values()),
            }
        )
        .sort_values("dist")
        .reset_index(drop=True)
    )
    return df_dist

# Cell
def get_mean_cross_entropy(df: pd.DataFrame, model: Model, n: Optional[int] = None):
    """
    Get the mean cross entropy for a model on an entire pandas dataframe

    :param df: the pandas dataframe containing each method to have the model predict on
    :param model: the model used to generate the predictions
    :param n: the number of methods to evaluate. If none, the entire dataframe will be used
    :returns: returns the mean cross entropy of the models predictions compared to true labels
    """
    if n is None:
        n = len(df)

    cross_entropy_losses = []
    # Need to change to sparse_categorical_crossentropy
    for mthd in df.code.values[:n]:
        # token the method and get the probabilities for each token from the model
        inputs = model.tokenize(mthd)
        probs = model.get_probs(inputs)[0].numpy()

        # calculate the cross entropy between the labels and probabilities
        losses = tf.keras.losses.sparse_categorical_crossentropy(
            inputs["input_ids"], probs
        ).numpy()
        cross_entropy_losses.append(losses)

    # flatten list of cross entropies and calculate the mean, median, std, and mad
    cross_entropy_losses = np.concatenate(cross_entropy_losses)
    return {
        "mean": np.mean(cross_entropy_losses),
        "median": np.median(cross_entropy_losses),
        "std": np.std(cross_entropy_losses),
        "mad": stats.median_abs_deviation(cross_entropy_losses),
    }

# Cell
_TRANSFORMs = {
    "randomized_tokens": code_token_randomizer,
    "randomized_lines": line_randomizer,
    "comments_removed": java_comment_remover,
}

# Cell
def _get_metrics(df, model):
    mean_probs = get_mean_probs(df, model)
    df_dist = mean_dist_probs(df, model)
    mean_cross_entropy = get_mean_cross_entropy(df, model)

    return {
        "mean_probs": mean_probs,
        "dist_mean": df_dist,
        "mean_cross_entropy": mean_cross_entropy,
    }


# def _long_range(data_dir, model, n=None):
#     long_range_results = {}

#     df_buggy = pd.read_json(data_dir / "buggy.jsonl", orient="records", lines=True)[:n]
#     long_range_results["buggy"] = _get_metrics(df_buggy, model)
#     del df_buggy

#     df_fixed = pd.read_json(data_dir / "fixed.jsonl", orient="records", lines=True)[:n]
#     long_range_results["fixed"] = _get_metrics(df_fixed, model)
#     del df_fixed

#     df_codesearchnet = pd.read_json(
#         data_dir / "codesearchnet_java" / "test.jsonl", orient="records", lines=True
#     )[:n]
#     long_range_results["codesearchnet_original"] = _get_metrics(df_codesearchnet, model)

#     for transform in _TRANSFORMs:
#         df_transformed = transform_df(df_codesearchnet, _TRANSFORMs[transform])
#         long_range_results["codesearchnet_" + transform] = _get_metrics(
#             df_transformed, model
#         )
#         del df_transformed

#     return long_range_results


def _long_range(bigclone_path, bugfix_path, codesearchnet_path, model, n=None):
    long_range_results = {}

    # TODO add bigclone data

    df_buggy = pd.read_json(bugfix_path / "buggy.jsonl", orient="records", lines=True)[
        :n
    ]
    long_range_results["buggy"] = _get_metrics(df_buggy, model)

    df_fixed = pd.read_json(bugfix_path / "fixed.jsonl", orient="records", lines=True)[
        :n
    ]
    long_range_results["fixed"] = _get_metrics(df_fixed, model)

    df_codesearchnet = pd.read_json(
        codesearchnet_path / "codesearchnet_java" / "test.jsonl",
        orient="records",
        lines=True,
    )[:n]
    long_range_results["codesearchnet_original"] = _get_metrics(df_codesearchnet, model)

    for transform in _TRANSFORMs:
        df_transformed = transform_df(df_codesearchnet, _TRANSFORMs[transform])
        long_range_results["codesearchnet_" + transform] = _get_metrics(
            df_transformed, model
        )

    return long_range_results


def _counterfactual(control_results, treatment_results):
    pass


def evaluate(data_path, model_path):
    """Function for evaluating models related to the library."""
    results = defaultdict(dict)
    #     models = []
    # These model folders will need to contain the config of the model as well
    # to differentiate them
    for m_path in model_path.glob("*/"):
        model = None
        print(m_path)
        if m_path.name == "Transformer":
            model = TransformerModel.from_path(m_path)
        elif "gru" in m_path.name:
            model = RNNModel.from_path(m_path)
        elif m_path.name == "RNN":
            pass

        bigclone_path = data_path / "bigclonebenchmark"
        bugfix_path = data_path / "bug_fix"
        codesearchnet_path = data_path / "codesearchnet"

        # Long-Range Interactions
        results[m_path.name]["long_range"] = _long_range(
            bigclone_path, bugfix_path, codesearchnet_path, model
        )

    return results
    # Counterfactuals


#         results[m_path]["counterfactual"] = _counterfactual(data_dir, model)
# _counterfactual(control_results, treatment_results)

# Save results in json format
# Long-Range Interactions
#     long_range_results = _long_range(data_dir, models)
#     long_range_results

#     # Counterfactuals
#     counterfactual_results = []
#     counterfactual_results
#     for transform in _TRANSFORMs:
#         pass
# _counterfactual(control_results, treatment_results)