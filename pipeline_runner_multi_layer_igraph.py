import os.path
import re
from typing import List

import matplotlib.pyplot as plt
from pm4py.algo.discovery.inductive import algorithm as inductive_miner
from pm4py.algo.filtering.log.attributes import attributes_filter
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.log.obj import EventLog
from pm4py.objects.petri_net.exporter import exporter as pnml_exporter

import clustering_variant
from apply_im import apply_im_with_noise_and_export, apply_im_without_noise_and_export, \
    apply_im_with_noise_and_export_post_process
from clustering_variant import ClusteringVariant
from distance_metrics import DistanceVariant
from file_writer_helper import run_start_string, get_config_string, get_result_header
from label_splitter_multi_layer_igraph import LabelSplitter
from performance_evaluator import PerformanceEvaluator
from pipeline_runner_single_layer_networkx import get_imprecise_labels, save_models_as_png
from post_processor import PostProcessor
from shared_constants import evaluated_models


def get_tuples_for_folder(folder_path, prefix):
    log_list = []
    identifier_pattern = f'^(\w+_\d+)'
    for f in os.listdir(folder_path):
        if 'LogD' in f:
            log_list.append((f'{prefix}/{re.match(identifier_pattern, f).group(1)}', f'{folder_path}{f}'))
    return log_list


def run_pipeline_multi_layer_igraph(input_models=evaluated_models) -> None:
    # apply_pipeline_to_folder([('real_logs/road_traffic_fines_N_W',
    #                            '/home/jonas/repositories/pm-label-splitting/example_logs/Road_Traffic_Fine_Management_Process_shortened_labels.xes.gz')],
    #                          'real_logs.txt',
    #                          labels_to_split=['F'],
    #                          use_frequency=False)

    mrt07_0946_list = get_tuples_for_folder('/home/jonas/repositories/pm-label-splitting/example_logs/imprInLoop_adaptive_OD/mrt07-0946/logs/', 'mrt07-0946')

    apply_pipeline_to_folder(mrt07_0946_list[1:],
                             'mrt07-0946.txt',
                             labels_to_split=[],
                             use_frequency=False)

    mrt05_1442_list = get_tuples_for_folder('/home/jonas/repositories/pm-label-splitting/example_logs/noImprInLoop_adaptive_OD/mrt05-1442/logs/', 'mrt05-1442')

    apply_pipeline_to_folder(mrt05_1442_list,
                             'mrt05-1442.txt',
                             labels_to_split=[],
                             use_frequency=False)


    feb19_1230_list = get_tuples_for_folder('/home/jonas/repositories/pm-label-splitting/example_logs/noImprInLoop_default_IMD/feb19-1230/logs/', 'feb19-1230')

    apply_pipeline_to_folder(feb19_1230_list,
                             'feb19-1230.txt',
                             labels_to_split=[],
                             use_frequency=False)


    feb16_1625_list = get_tuples_for_folder('/home/jonas/repositories/pm-label-splitting/example_logs/noImprInLoop_default_OD/feb16-1625/logs/', 'feb16-1625')

    apply_pipeline_to_folder(feb16_1625_list,
                             'feb16-1625.txt',
                             labels_to_split=[],
                             use_frequency=False)


def plot_noise_to_f1_score(x_noise, y_unrefined, y_refined, input_name):
    plt.plot(x_noise, y_unrefined, 'bo', label='Unrefined Log')
    plt.plot(x_noise, y_refined, 'ro', label='Refined Log')
    plt.axis([0, 0.5, 0, 1])
    plt.xlabel('Noise Threshold')
    plt.ylabel('F1 Score')
    plt.legend(loc="lower right")
    plt.grid()
    plt.savefig(f'/mnt/c/Users/Jonas/Desktop/pm-label-splitting/plots/{input_name}_noise_to_f1_score.png')


def get_xixi_metrics(input_name, log_path, labels_to_split):
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        xixi_refined_log_path = log_path.replace('LogD', 'LogR', 1)
        if not os.path.isfile(xixi_refined_log_path):
            xixi_refined_log_path = xixi_refined_log_path.replace('LogR', 'LogR_IM', 1)

        log = xes_importer.apply(xixi_refined_log_path)
        for trace in log:
            for event in trace:
                if event['concept:name'][0] in labels_to_split:
                    event['concept:name'] = event['concept:name'][0]
        outfile.write('\n Xixi refined log results:\n')
        precision = apply_im_without_noise_and_export(input_name, 'xixi', log, outfile)
        return precision


def apply_pipeline_to_folder(input_list, summary_file, labels_to_split=[], use_frequency=False):
    for (name, path) in input_list:
        best_precision, best_configs, xixi_precision, golden_standard_precision = apply_pipeline_multi_layer_igraph_to_log_with_multiple_parameters(
            name,
            labels_to_split,
            path,
            20000000,
            use_frequency=use_frequency)
        summary_file_name = summary_file
        with open(f'./outputs/best_results/With_Parameters_{summary_file_name}', 'a') as outfile:
            outfile.write(get_result_header(name))

            outfile.write(f'\nBest found configs for {name}:')
            for config in best_configs:
                outfile.write(config)
            outfile.write('Precision:\n')
            outfile.write(str(best_precision))
        with open(f'./outputs/best_results/{summary_file_name}', 'a') as outfile:
            outfile.write(f'\n\nBest precision found for {name}:\n')
            outfile.write(f'{str(best_precision)}\n')
            if xixi_precision != 0:
                outfile.write(f'Precision found by Xixi for {name}:\n')
                outfile.write(f'{str(xixi_precision)}\n')
            if golden_standard_precision != 0:
                outfile.write(f'Golden_standard_precision for {name}:\n')
                outfile.write(f'{str(golden_standard_precision)}\n')


def apply_pipeline_multi_layer_igraph_to_log_with_multiple_parameters(input_name: str,
                                                                      labels_to_split: List[str],
                                                                      log_path: str,
                                                                      max_number_of_traces: int,
                                                                      use_frequency=False):
    input_name = f'{input_name}_VARIANTS_ONLY' if use_frequency else f'{input_name}_VARIANTS_ONLY_N_W'
    original_log = xes_importer.apply(log_path)

    xixi_precision = 0
    golden_standard_precision = 0

    if not labels_to_split:
        labels_to_split = get_imprecise_labels(original_log)
        xixi_precision = get_xixi_metrics(input_name, log_path, labels_to_split)
        golden_standard_precision = evaluate_golden_standard_model(input_name, log_path, labels_to_split)
        print('golden_standard_precision')
        print(golden_standard_precision)
        export_model_from_original_log_with_precise_labels(input_name, log_path)

    y_f1_scores_unrefined = write_data_from_original_log_with_imprecise_labels(input_name, original_log)

    if max_number_of_traces < 20000000:
        log = xes_importer.apply(
            log_path,
            parameters={
                xes_importer.Variants.ITERPARSE.value.Parameters.MAX_TRACES: max_number_of_traces})
        xes_exporter.apply(log, f'/home/jonas/repositories/pm-label-splitting/outputs/{input_name}_used_log.xes')

    best_precision = 0
    best_configs = []
    y_f1_scores_refined = []
    x_noises = [0, 0.1, 0.2, 0.3, 0.4]

    for label in labels_to_split:
        for window_size in [2, 3, 4]:
            for distance in [DistanceVariant.EDIT_DISTANCE, DistanceVariant.SET_DISTANCE,
                             DistanceVariant.MULTISET_DISTANCE]:
                for threshold in [0]:
                    log = xes_importer.apply(
                        log_path,
                        parameters={
                            xes_importer.Variants.ITERPARSE.value.Parameters.MAX_TRACES: max_number_of_traces})

                    precision, f1_scores_refined = apply_pipeline_multi_layer_igraph_to_log(input_name,
                                                                                            log,
                                                                                            [label],
                                                                                            original_log=original_log,
                                                                                            threshold=threshold,
                                                                                            window_size=window_size,
                                                                                            number_of_traces=max_number_of_traces,
                                                                                            distance_variant=distance,
                                                                                            original_log_path=log_path,
                                                                                            best_precision=best_precision,
                                                                                            use_frequency=use_frequency)
                    if len(f1_scores_refined) > 0:
                        y_f1_scores_refined = f1_scores_refined

                    if precision > best_precision:
                        best_configs = [get_config_string(clustering_variant.ClusteringVariant.COMMUNITY_DETECTION,
                                                          distance,
                                                          labels_to_split,
                                                          max_number_of_traces,
                                                          log_path,
                                                          threshold,
                                                          window_size,
                                                          use_frequency=use_frequency)]
                        best_precision = precision
                    elif round(precision, 2) == round(best_precision, 2):
                        best_configs.append(get_config_string(clustering_variant.ClusteringVariant.COMMUNITY_DETECTION,
                                                              distance,
                                                              labels_to_split,
                                                              max_number_of_traces,
                                                              log_path,
                                                              threshold,
                                                              window_size,
                                                              use_frequency=use_frequency))

    print('best_precision of all iterations:')
    print(best_precision)

    plot_noise_to_f1_score(x_noises, y_f1_scores_unrefined, y_f1_scores_refined, input_name)
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        outfile.write('Best precision found:\n')
        outfile.write(str(best_precision))
    return best_precision, best_configs, xixi_precision, golden_standard_precision


def write_data_from_original_log_with_imprecise_labels(input_name, original_log):
    print(f'./outputs/{input_name}.txt')
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        print(f'Starting pipeline for {input_name}')
        outfile.write(run_start_string())
        outfile.write('\nOriginal Data Performance:\n')
        f1_scores = apply_im_with_noise_and_export(input_name, 'original_log_imprecise_labels', original_log, outfile)
        apply_im_without_noise_and_export(input_name, 'original_log_imprecise_labels', original_log, outfile)
    return f1_scores


def export_model_from_original_log_with_precise_labels(input_name, path):
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        outfile.write('\n Data from log without imprecise labels\n')
        original_input_name = input_name.replace('_VARIANTS_ONLY', '')
        original_input_name = re.sub(r'.*/', '', original_input_name)

        pattern = original_input_name + r'.*'
        log_path = re.sub(pattern, f'{original_input_name}_Log.xes.gz', path)
        original_log = xes_importer.apply(log_path)
        apply_im_with_noise_and_export(input_name, 'original_log_precise_labels', original_log, outfile)
        apply_im_without_noise_and_export(input_name, 'original_log_precise_labels', original_log, outfile)


def evaluate_golden_standard_model(input_name, path, labels_to_split):
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        outfile.write('\n Performance of golden standard model:\n')

        print(path)
        imprecise_log = xes_importer.apply(path)
        original_input_name = input_name.replace('_VARIANTS_ONLY(_N_W)?', '')
        original_input_name = re.sub(r'.*/', '', original_input_name)

        pattern = original_input_name + r'.*'
        log_path = re.sub(pattern, f'{original_input_name}_Log.xes.gz', path)
        print(log_path)
        log = xes_importer.apply(log_path)

        imprecise_activities = attributes_filter.get_attribute_values(imprecise_log, 'concept:name')
        print(imprecise_activities)

        net, initial_marking, final_marking = inductive_miner.apply(log)

        for transition in net.transitions:
            if transition.label not in imprecise_activities:
                transition.label = labels_to_split[0]

        performance_evaluator = PerformanceEvaluator(net, initial_marking, final_marking, imprecise_log,
                                                     outfile)
        performance_evaluator.evaluate_performance()

        original_tree = inductive_miner.apply_tree(log)
        pnml_exporter.apply(net, initial_marking,
                            f'/home/jonas/repositories/pm-label-splitting/outputs/{input_name}_no_noise_golden.pnml',
                            final_marking=final_marking)
        save_models_as_png(f'{input_name}_no_noise_golden',
                           final_marking,
                           initial_marking,
                           net,
                           original_tree)

        return performance_evaluator.precision


def apply_pipeline_multi_layer_igraph_to_log(input_name: str,
                                             log: EventLog,
                                             labels_to_split: list[str],
                                             original_log: EventLog,
                                             threshold: float = 0.5,
                                             window_size: int = 3,
                                             number_of_traces: int = 100000,
                                             distance_variant: DistanceVariant = DistanceVariant.EDIT_DISTANCE,
                                             clustering_variant: ClusteringVariant = ClusteringVariant.COMMUNITY_DETECTION,
                                             original_log_path: str = '',
                                             best_precision: float = 0,
                                             use_frequency=False
                                             ) -> float:
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        outfile.write(get_config_string(clustering_variant, distance_variant, labels_to_split, number_of_traces,
                                        original_log_path, threshold, window_size, use_frequency))

        label_splitter = LabelSplitter(outfile,
                                       labels_to_split,
                                       threshold=threshold,
                                       window_size=window_size,
                                       distance_variant=distance_variant,
                                       clustering_variant=clustering_variant,
                                       use_frequency=use_frequency)
        split_log = label_splitter.split_labels(log)

        net, initial_marking, final_marking = inductive_miner.apply(split_log)
        tree = inductive_miner.apply_tree(split_log)

        post_processor = PostProcessor(label_splitter.get_split_labels_to_original_labels())
        final_net = post_processor.post_process_petri_net(net)

        outfile.write('\nPerformance split_log:\n')
        outfile.write('\nIM without threshold:\n')
        performance_evaluator = PerformanceEvaluator(final_net, initial_marking, final_marking, original_log, outfile)
        performance_evaluator.evaluate_performance()

        f1_scores_refined = []
        if performance_evaluator.precision > best_precision:
            print(f'\nHigher Precision found: {performance_evaluator.precision}')
            outfile.write('\nIM with noise threshold:\n')

            f1_scores_refined = apply_im_with_noise_and_export_post_process(input_name, 'split_log', split_log, original_log, outfile,
                                                                            label_splitter.get_split_labels_to_original_labels())

            xes_exporter.apply(split_log,
                               f'/home/jonas/repositories/pm-label-splitting/outputs/{input_name}_split_log.xes')
            pnml_exporter.apply(final_net, initial_marking,
                                f'/home/jonas/repositories/pm-label-splitting/outputs/{input_name}_petri_net.pnml',
                                final_marking=final_marking)
            save_models_as_png(f'{input_name}_refined_process', final_marking, initial_marking, net, tree)
        return performance_evaluator.precision, f1_scores_refined
