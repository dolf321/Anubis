import React, {useState} from 'react';
import Button from '@material-ui/core/Button';
import TextField from '@material-ui/core/TextField';
import Dialog from '@material-ui/core/Dialog';
import DialogActions from '@material-ui/core/DialogActions';
import DialogContent from '@material-ui/core/DialogContent';
import DialogContentText from '@material-ui/core/DialogContentText';
import DialogTitle from '@material-ui/core/DialogTitle';
import {makeStyles} from "@material-ui/core/styles";
import {Redirect} from "react-router-dom";

const useStyles = makeStyles(theme => ({
  dialog: {
    margin: theme.spacing(2),
    padding: theme.spacing(2)
  },
}));

export default function Auth(props) {
  const classes = useStyles();
  const [netid, setNetid] = useState('');
  const [code, setCode] = useState('');
  const [redirect, setRedirect] = useState(false);
  const {
    open,
    onClose,
  } = props;

  if (redirect) {
    return (
      <Redirect to={`/fq/${code}/${netid}`}/>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} className={classes.dialog}>
      <DialogTitle>
        Verification
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          Please verify your netid and Anubis code to see your exam questions <br/>
        </DialogContentText>
        <TextField
          required
          autoFocus
          fullWidth
          margin={'dense'}
          variant={'outlined'}
          label={'netid'}
          onChange={e => setNetid(e.target.value.trim())}
          onKeyPress={e => e.key === 'Enter' ? setRedirect(true) : null}
        />
        <TextField
          required
          fullWidth
          margin={'dense'}
          variant={'outlined'}
          label={'code'}
          onChange={e => setCode(e.target.value.trim())}
          onKeyPress={e => e.key === 'Enter' ? setRedirect(true) : null}
        />
      </DialogContent>
      <DialogActions>
        <Button variant="contained" color="primary" onClick={() => setRedirect(true)}>
          Verify
        </Button>
      </DialogActions>
    </Dialog>
  );
}