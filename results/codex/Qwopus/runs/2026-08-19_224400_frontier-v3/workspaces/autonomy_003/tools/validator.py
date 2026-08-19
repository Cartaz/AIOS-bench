STATE={'runs':0}
def validate():
    STATE['runs']+=1
    if STATE['runs']==3:
        raise RuntimeError('validator state corruption: counter=3')
    return True
