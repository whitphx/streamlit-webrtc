import { Streamlit } from "streamlit-component-lib";
import React, { useEffect } from "react";
import { makeStyles } from "@material-ui/core/styles";
import Paper from "@material-ui/core/Paper";
import CircularProgress from "@material-ui/core/CircularProgress";
import VideoLabelIcon from "@material-ui/icons/VideoLabel";

const useStyles = makeStyles((theme) => ({
  paper: {
    padding: theme.spacing(4),
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    width: "100%",
  },
}));

interface PlaceholderProps {
  loading: boolean;
}
const Placeholder: React.VFC<PlaceholderProps> = (props) => {
  useEffect(() => {
    Streamlit.setFrameHeight();
  });

  const classes = useStyles();

  return (
    <Paper className={classes.paper} elevation={0}>
      {props.loading ? (
        <CircularProgress />
      ) : (
        <VideoLabelIcon fontSize="large" />
      )}
    </Paper>
  );
};

export default React.memo(Placeholder);
