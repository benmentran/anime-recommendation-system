#!/bin/bash
C=netflix-movie-recommendation-system-recommend_service-1
docker exec "$C" ls -la /app/model/ 2>&1
docker exec "$C" python -c "
import pickle
try:
    d = pickle.load(open('/app/model/popular.pkl','rb'))
    print('popular OK, len=', len(d), 'head=', d[:3])
except Exception as e:
    print('popular FAIL:', type(e).__name__, e)
try:
    import numpy; print('numpy', numpy.__version__)
except Exception as e:
    print('numpy FAIL', e)
" 2>&1
