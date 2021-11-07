import os
import re

from pm4py.objects.log.importer.xes import importer as xes_importer

from apply_im import apply_im_without_noise_and_export, apply_im_without_noise
from model_comparer import ModelComparer


def get_xixi_metrics(input_name, log_path, labels_to_split, g_net, g_im, g_fm):
    with open(f'./outputs/{input_name}.txt', 'a') as outfile:
        original_log = xes_importer.apply(log_path)
        xixi_refined_log_path = log_path.replace('LogD', 'LogR', 1)
        if not os.path.isfile(xixi_refined_log_path):
            xixi_refined_log_path = xixi_refined_log_path.replace('LogR', 'LogR_IM', 1)

        log = xes_importer.apply(xixi_refined_log_path)
        labels_to_original = {}

        for trace in log:
            for event in trace:
                print('concept:name')
                print(event['concept:name'])

        for label in labels_to_split:
            labels_to_original[label] = label


        outfile.write('\n Xixi refined log results:\n')
        precision, final_net, initial_marking, final_marking = apply_im_without_noise_and_export(input_name, 'xixi', log, original_log, outfile, labels_to_original=labels_to_original)

        model_comparer = ModelComparer(g_net, g_im, g_fm, final_net, initial_marking, final_marking, log, outfile, precision)
        s_precision, s_recall = model_comparer.compare_models()
    return precision + s_precision + s_recall


def get_tuples_for_folder(folder_path, prefix):
    log_list = []
    identifier_pattern = f'^(\w+_\d+)'
    for f in os.listdir(folder_path):
        if 'LogD' in f:
            log_list.append((f'{prefix}/{re.match(identifier_pattern, f).group(1)}', f'{folder_path}{f}'))
    return log_list