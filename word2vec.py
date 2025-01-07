from gensim.models import Word2Vec
import json

def find_similar_words(model, word, topn=10):
    similar_words = model.wv.most_similar(
        positive=[word],
        topn=topn,
        restrict_vocab=None
    )
    return similar_words
