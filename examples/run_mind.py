import sys
sys.path.append("../")

import pandas as pd
from deepmatch_torch.models import FM, DSSM, NCF, MIND

from deepctr_torch.inputs import SparseFeat, VarLenSparseFeat
from preprocess import gen_data_set_youteube, gen_model_input, gen_data_set
from sklearn.preprocessing import LabelEncoder
import torch.nn.functional as F 


if __name__ == "__main__":

    data = pd.read_csvdata = pd.read_csv("./movielens_sample.txt")
    sparse_features = ["movie_id", "user_id",
                       "gender", "age", "occupation", "zip", ]
    SEQ_LEN = 50

    # 1.Label Encoding for sparse features,and process sequence features with `gen_date_set` and `gen_model_input`

    features = ['user_id', 'movie_id', 'gender', 'age', 'occupation', 'zip']
    feature_max_idx = {}
    for feature in features:
        lbe = LabelEncoder()
        data[feature] = lbe.fit_transform(data[feature]) + 1
        feature_max_idx[feature] = data[feature].max() + 1
    
    user_profile = data[["user_id", "gender", "age", "occupation", "zip"]].drop_duplicates('user_id')

    item_profile = data[["movie_id"]].drop_duplicates('movie_id')

    user_profile.set_index("user_id", inplace=True)

    user_item_list = data.groupby("user_id")['movie_id'].apply(list)

    train_set, test_set = gen_data_set_youteube(data, 5)
    # train_set, test_set = gen_data_set(data, 5)

    train_model_input, train_label = gen_model_input(train_set, user_profile, SEQ_LEN)
    test_model_input, test_label = gen_model_input(test_set, user_profile, SEQ_LEN)


    # 2.count #unique features for each sparse field and generate feature config for sequence feature

    embedding_dim = 16

    user_feature_columns = [SparseFeat('user_id', feature_max_idx['user_id'], embedding_dim),
                            SparseFeat("gender", feature_max_idx['gender'], embedding_dim),
                            SparseFeat("age", feature_max_idx['age'], embedding_dim),
                            SparseFeat("occupation", feature_max_idx['occupation'], embedding_dim),
                            SparseFeat("zip", feature_max_idx['zip'], embedding_dim),
                            VarLenSparseFeat(SparseFeat('hist_movie_id', vocabulary_size=feature_max_idx['movie_id'], 
                                        embedding_dim=embedding_dim, embedding_name="movie_id"), maxlen=10, combiner='mean')
                            # VarLenSparseFeat(SparseFeat('hist_movie_id', feature_max_idx['movie_id'], embedding_dim,
                            #                             embedding_name="movie_id"), SEQ_LEN, 'mean', 'hist_len'),
                            ]

    item_feature_columns = [
        VarLenSparseFeat(SparseFeat('movie_id', feature_max_idx['movie_id'], embedding_dim, embedding_name="movie_id"), maxlen=6, combiner='mean')]

    # item_feature_columns = [
    #     SparseFeat('movie_id', feature_max_idx['movie_id'], embedding_dim, embedding_name="movie_id")]

    # 3.Define Model and train

    # model = YouTubeDNN(user_feature_columns, item_feature_columns, num_sampled=5, user_dnn_hidden_units=(64, embedding_dim))
    model = MIND(user_feature_columns,item_feature_columns,
                    dynamic_k=False, p=1, k_max=2, num_sampled=5,
                    user_dnn_hidden_units=(64, embedding_dim),
                    criterion=F.cross_entropy,
                optimizer='Adam',    
                config={
                    'device': 'cpu',
                    "gpus": 0
                }
    )  

    model.fit(train_model_input, train_label, 
                        max_epochs=10, batch_size=128 )
    # model.compile(optimizer="adam", loss=sampledsoftmaxloss)  # "binary_crossentropy")
    # model.compile(optimizer='adagrad', loss="cross_entropy")
    # history = model.fit(train_model_input, train_label,  # train_label,
                        # batch_size=227, epochs=1, verbose=1, validation_split=0.0, )

    # 4. Generate user features for testing and full item features for retrieval
    test_user_model_input = test_model_input
    model.mode = "user_representation"
    user_embedding_model = model

    user_embs = user_embedding_model.full_predict(test_user_model_input, batch_size=2)
    print(user_embs.shape)

    model.mode = "item_representation"
    all_item_model_input = {"movie_id": item_profile['movie_id'].values}
    item_embedding_model = model.rebuild_feature_index(item_feature_columns)
    item_embs = item_embedding_model.full_predict(all_item_model_input, batch_size=2 ** 12)
    print(item_embs.shape)
    
    # test_user_model_input = test_model_input
    # all_item_model_input = {"movie_id": item_profile['movie_id'].values}

    # user_embedding_model = Model(inputs=model.user_input, outputs=model.user_embedding)
    # item_embedding_model = Model(inputs=model.item_input, outputs=model.item_embedding)

    # user_embs = user_embedding_model.predict(test_user_model_input, batch_size=2 ** 12)
    # # user_embs = user_embs[:, i, :]  # i in [0,k_max) if MIND
    # item_embs = item_embedding_model.predict(all_item_model_input, batch_size=2 ** 12)

    # print(user_embs.shape)
    # print(item_embs.shape)

    # 5. [Optional] ANN search by faiss  and evaluate the result

    # test_true_label = {line[0]:[line[2]] for line in test_set}
    #
    # import numpy as np
    # import faiss
    # from tqdm import tqdm
    # from deepmatch.utils import recall_N
    #
    # index = faiss.IndexFlatIP(embedding_dim)
    # # faiss.normalize_L2(item_embs)
    # index.add(item_embs)
    # # faiss.normalize_L2(user_embs)
    # D, I = index.search(np.ascontiguousarray(user_embs), 50)
    # s = []
    # hit = 0
    # for i, uid in tqdm(enumerate(test_user_model_input['user_id'])):
    #     try:
    #         pred = [item_profile['movie_id'].values[x] for x in I[i]]
    #         filter_item = None
    #         recall_score = recall_N(test_true_label[uid], pred, N=50)
    #         s.append(recall_score)
    #         if test_true_label[uid] in pred:
    #             hit += 1
    #     except:
    #         print(i)
    # print("recall", np.mean(s))
    # print("hr", hit / len(test_user_model_input['user_id']))